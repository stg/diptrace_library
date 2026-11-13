"""Destination plans preserve full style equivalence and distinct resources."""
from decimal import Decimal
import unittest
from unittest.mock import patch

from lib.common.model import Value
from lib.common.units import XmlUnits
from lib.common.footprint_objects import new_pad, new_pattern
from lib.common.xml import set_attribute
from lib.common.xml_catalog import StyleTable, StylePlans, record_key
from lib.common.xml_pad_output import project_pad_style, plan_pad_style
from lib.common.xml_plan import XmlBuilder, XmlPlan


class XmlPlanTests(unittest.TestCase):
    def test_builder_composes_frozen_subtrees_without_rebuilding_them(self):
        shared = XmlPlan('Item', (Value.of('shared'),))
        builder = XmlBuilder('Data')
        builder.append(shared)
        builder.add('Other', 2)
        plan = builder.freeze()
        self.assertIs(plan.children[0], shared)
        builder.add('Later', 3)
        self.assertEqual(tuple(child.kind for child in plan.children), ('Item', 'Other'))
        with self.assertRaises(TypeError):
            builder.append(object())

    def test_style_plan_snapshots_survive_later_resource_additions(self):
        table = StylePlans('Styles', 'Style', 'Name', 'Style')
        first = table.include_plan(XmlPlan('Style', (Value.of('first'),)))
        old = table.plan
        self.assertIs(table.plan, old)
        old_element = table.element
        table.include_plan(XmlPlan('Style', (Value.of('second'),)))
        self.assertEqual(len(old.children), 1)
        self.assertEqual(old.children[0].attribute('Name'), first)
        self.assertEqual(len(old_element.children()), 1)
        self.assertEqual(len(table.plan.children), 2)
        self.assertEqual(record_key(table.element), table.plan.key())

    def test_schematic_library_keeps_definitions_as_plans_until_inspection(self):
        from lib import new_schematic
        from lib.schematic.formats.dchxml.library import project_library
        from lib.schematic.model.objects import new_symbol, new_pin
        document = new_schematic()
        schematic = document.one('/Schematic')
        part = schematic.one('Components').append(new_symbol('Device', 'U1'))
        part.one('Pins').append(new_pin())
        for version in (46, 47, 48, 52):
            with self.subTest(version=version):
                with patch.object(XmlPlan, 'element', side_effect=AssertionError('library materialized')):
                    library = project_library(schematic, units=XmlUnits('mm'), version=version)
                self.assertEqual(len(library.component_styles), 1)
                self.assertEqual(library.plan.key(), record_key(library.element))
                self.assertIs(library.element, library.element)

    def test_compatibility_font_replacement_keeps_attribute_order_and_integer_type(self):
        from lib.common.model import Element
        from lib.common.xml_font_output import project_size
        source = Element('Shape')
        source.add('FontSize', Decimal('5.0000'))
        for target in (Element('Font'), XmlBuilder('Font')):
            set_attribute(target, 'Size', Decimal('5.0'))
            set_attribute(target, 'Width', -2)
            set_attribute(target, 'Scale', 1)
            project_size(source, target, legacy='Size', fractional=False)
            plan = target.freeze() if isinstance(target, XmlBuilder) else XmlPlan.from_element(target)
            self.assertEqual(tuple(name for name, _ in plan.attributes), ('Size', 'Width', 'Scale'))
            self.assertIs(type(plan.attributes[0][1].value), int)

    def test_schematic_pattern_plans_match_standalone_editable_helpers(self):
        from lib.schematic.model.objects import new_pattern
        from lib.schematic.formats.dchxml.patterns import plan_pattern, project_pattern
        pattern = new_pattern('Footprint')
        pattern.one('Model3D/Offset')['Y'] = Decimal('2.5')
        for version in (46, 48, 52):
            options = dict(style='', default_pad_style='Default', pad_styles={},
                           units=XmlUnits('mil'), version=version)
            expected = record_key(project_pattern(pattern, **options))
            self.assertEqual(plan_pattern(pattern, **options).key(), expected)

    def test_pcb_pattern_projection_stays_a_plan_until_element_is_requested(self):
        from lib.pcb.tests.test_dip_output import configured_document
        from lib.pcb.formats.dipxml.pattern_output import project_pattern
        pattern = configured_document().one('/Board/Components/Component/Pattern')
        with patch.object(XmlPlan, 'element', side_effect=AssertionError('premature materialization')):
            projection = project_pattern(pattern, style='', units=XmlUnits('mm'))
        self.assertEqual(record_key(projection.element), projection.plan.key())
        self.assertIs(projection.element, projection.element)

    def test_symbol_plans_match_editable_projection_in_each_vocabulary(self):
        from lib.schematic.model.objects import new_symbol, new_pin, new_symbol_shape
        from lib.schematic.formats.dchxml.symbols import plan_symbol, project_symbol
        part = new_symbol('Device', 'R', placed=False)
        pin = part.one('Pins').append(new_pin())
        pin['NameFontSize'] = Decimal('2.75')
        shape = part.one('Shapes').append(new_symbol_shape())
        shape['Type'], shape['FontSize'] = 10, Decimal('3.25')
        shape.one('TextLine').add('pt', 'first line')
        shape.one('TextLine').add('pt', 'second line')
        part['Component_CategoryName'] = 'Passives'
        for version in (46, 47, 52):
            for units in ('mm', 'mil', 'inch'):
                with self.subTest(version=version, units=units):
                    options = dict(units=XmlUnits(units), version=version)
                    element = project_symbol(part, **options)
                    plan = plan_symbol(part, **options)
                    self.assertEqual(plan.key(), record_key(element))
                    self.assertEqual(record_key(plan.element()), record_key(element))

    def test_category_key_allocation_updates_only_the_detached_plan(self):
        from lib.common.xml_catalog import CategoryCatalog
        root = XmlBuilder('Part')
        category = root.add('Category')
        category.add('Name', 'Components')
        original = root.freeze()
        catalog = CategoryCatalog()
        replacement = catalog.include_plan(original.child('Category'))
        updated = original.with_child(original.child('Category'), replacement)
        self.assertEqual(updated.child('Category').attribute('Index'), 0)
        self.assertEqual(original.child('Category').attributes, ())
        self.assertEqual(XmlPlan.from_element(updated.element()).key(), updated.key())
        with self.assertRaises(ValueError):
            original.with_child(XmlPlan('Absent'), replacement)

    def test_local_plans_reach_the_global_table_without_intermediate_trees(self):
        plan = plan_pad_style(new_pad(), name='', units=XmlUnits('mm'))
        local = StylePlans('PadStyles', 'PadStyle', 'Name', 'Local')
        with patch.object(XmlPlan, 'element', side_effect=AssertionError('local style materialized')):
            local_key = local.include_plan(plan)
            self.assertEqual(local.include_plan(plan), local_key)
            self.assertEqual(local.entries, [(local_key, plan)])
        table = StyleTable('PadStyles', 'PadStyle', 'Name', 'Global')
        global_key = table.include_plan(local.entries[0][1])
        self.assertEqual(len(table.element.children()), 1)
        self.assertEqual(table.element.one('PadStyle')['Name'], global_key)
        self.assertEqual(local.element.one('PadStyle')['Name'], local_key)

    def test_pad_plan_matches_the_existing_complete_style_key(self):
        for source in (new_pad(), new_pattern()):
            for units in ('mm', 'mil', 'inch'):
                with self.subTest(kind=source.kind, units=units):
                    scale = XmlUnits(units)
                    node = project_pad_style(source, name='', units=scale)
                    plan = plan_pad_style(source, name='', units=scale)
                    self.assertEqual(plan.key(), record_key(node))
                    self.assertEqual(record_key(plan.element()), record_key(node))

    def test_plan_and_editable_style_paths_share_one_resource_table(self):
        scale = XmlUnits('mm')
        source = new_pad()
        plan = plan_pad_style(source, name='', units=scale)
        table = StyleTable('PadStyles', 'PadStyle', 'Name', 'Pad')
        first = table.include_plan(plan)
        with patch.object(XmlPlan, 'element', side_effect=AssertionError('duplicate plan materialized')):
            self.assertEqual(table.include_plan(plan), first)
        self.assertEqual(table.include(project_pad_style(source, name='', units=scale)), first)
        second = table.include_plan(plan, exclude=(first,))
        self.assertNotEqual(first, second)
        third = table.include_plan(plan, name='Explicit')
        self.assertEqual(third, 'Explicit')
        self.assertEqual(len(table.element.children()), 3)
        with self.assertRaises(ValueError):
            table.include_plan(plan, name='Explicit')

    def test_override_is_detached_and_preserves_types_and_order(self):
        builder = XmlBuilder('Style')
        set_attribute(builder, 'Width', Decimal('1.2500'))
        set_attribute(builder, 'Side', 'Top')
        builder.add('Text', 'text')
        plan = builder.freeze()
        changed = plan.with_attribute('Side', 'Bottom')
        self.assertEqual(plan.attribute('Side'), 'Top')
        self.assertEqual(changed.attribute('Side'), 'Bottom')
        self.assertEqual(tuple(name for name, _ in changed.attributes), ('Width', 'Side'))
        self.assertEqual(changed.key(), record_key(changed.element()))
        self.assertEqual(plan.attributes[0][1], Value.of(Decimal('1.2500')))
        with self.assertRaises(KeyError):
            plan.attribute('Missing')


if __name__ == '__main__':
    unittest.main()
