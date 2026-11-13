"""Generated XML plans use the ordinary codec's spelling and strict types."""
from dataclasses import replace
from decimal import Decimal
import unittest
from unittest.mock import patch

from lib.common.model import Document, Element, Value
from lib.common.xml import XmlDialect, dumps, dumps_plan, render_plan
from lib.common.xml_plan import XmlBuilder, XmlPlan


class XmlPlanSerializationTests(unittest.TestCase):
    dialect = XmlDialect(source_type='Test', number_attributes=frozenset(('X',)),
                         boolean_attributes=frozenset(('Enabled',)),
                         number_text=frozenset((('Data', 'Size'),)), boolean_text=frozenset(('Visible',)))

    def source(self):
        source = XmlBuilder('Source')
        source.attribute('Type', 'Test')
        source.attribute('Label', 'quote " and < &\t\n\r')
        data = source.add('Data')
        data.attribute('X', Decimal('-0.0000'))
        data.attribute('Enabled', False)
        data.add('Size', Decimal('1.2500'))
        data.add('Visible', True)
        data.add('Text', 'A < B & C\rD')
        data.add('Empty')
        data.add('Blank', '')
        return source.freeze()

    def test_document_bytes_match_editable_output_without_allocating_elements(self):
        source = self.source()
        document = Document()
        document.root.append(source.element())
        for newline in ('\n', '\r\n'):
            for canonical in (False, True):
                options = dict(newline=newline, canonical_numbers=canonical, dialect=self.dialect)
                expected = dumps(document, **options)
                with patch.object(XmlPlan, 'element', side_effect=AssertionError('editable materialization')):
                    self.assertEqual(dumps_plan(source, **options), expected)

    def test_both_families_library_fragments_match_their_editable_serialization(self):
        from lib.common.units import XmlUnits
        from lib.schematic.formats.dchxml.patterns import plan_pattern
        from lib.schematic.formats.dchxml.syntax import DIALECT as schematic_dialect
        from lib.schematic.model.objects import new_pattern
        from lib.pcb.formats.dipxml.pattern_output import project_pattern
        from lib.pcb.formats.dipxml.syntax import DIALECT as pcb_dialect
        from lib.pcb.tests.test_dip_output import configured_document
        schematic = new_pattern('Footprint')
        pcb = configured_document().one('/Board/Components/Component/Pattern')
        for units in ('mm', 'mil', 'inch'):
            scale = XmlUnits(units)
            plans = [(plan_pattern(schematic, style='Pattern', default_pad_style='Default',
                                   pad_styles={}, units=scale, version=version), schematic_dialect)
                     for version in (46, 48, 52)]
            plans.append((project_pattern(pcb, style='Pattern', units=scale).plan, pcb_dialect))
            for plan, dialect in plans:
                source = XmlPlan('Source', attributes=(('Type', Value.of(dialect.source_type)),), children=(plan,))
                document = Document()
                document.root.append(source.element())
                options = dict(dialect=dialect, canonical_numbers=True)
                with self.subTest(units=units, family=dialect.format):
                    self.assertEqual(dumps_plan(source, **options), dumps(document, **options))

    def test_snapshot_rejects_content_it_cannot_represent_in_order(self):
        mixed = Element('Text', 'before')
        mixed.add('Inline', 'inside')
        mixed._items.append(Value.of('after'))
        with self.assertRaisesRegex(ValueError, 'mixed element/text'):
            XmlPlan.from_element(mixed)
        comment = Element('Comment', 'text')
        comment.annotations['xml_role'] = 'comment'
        with self.assertRaisesRegex(ValueError, 'ordinary element'):
            XmlPlan.from_element(comment)

    def test_leading_text_and_nested_elements_keep_their_order(self):
        mixed = Element('Text', 'before')
        mixed.add('Inline', 'inside')
        plan = XmlPlan.from_element(mixed)
        self.assertEqual(render_plan(plan), '<Text>before<Inline>inside</Inline></Text>')

    def test_source_type_uses_content_not_inspection_metadata(self):
        source = self.source()
        typed = replace(Value.of('Test'), lexeme='Test')
        source = replace(source, attributes=(('Type', typed),))
        self.assertIn('Type="Test"', dumps_plan(source, dialect=self.dialect))
        with self.assertRaisesRegex(ValueError, 'Type="Test"'):
            dumps_plan(source.with_attribute('Type', 'Other'), dialect=self.dialect)
        with self.assertRaisesRegex(ValueError, 'Source element'):
            dumps_plan(XmlPlan('Other'))

    def test_invalid_generated_content_is_checked_on_every_emission(self):
        cases = (
            (XmlPlan('Bad Name'), ValueError, 'element name'),
            (XmlPlan('Data', attributes=(('X', Value.of(1)), ('X', Value.of(2)))), ValueError, 'duplicate'),
            (XmlPlan('Data', attributes=(('X', Value.of('1')),)), ValueError, 'XML number'),
            (XmlPlan('Data', attributes=(('Enabled', Value.of(0)),)), ValueError, 'XML boolean'),
            (XmlPlan('Visible', (Value.of('Y'),)), ValueError, 'XML boolean'),
            (XmlPlan('Data', children=(XmlPlan('Size', (Value.of('1'),)),)), ValueError, 'XML number'),
            (XmlPlan('Data', attributes=(('X', Value(1, 'number', unit='mm')),)), ValueError, 'unit suffix'),
            (XmlPlan('Text', (Value.of('\x00'),)), ValueError, 'XML 1.0'),
            (XmlPlan('Data', attributes=(('X', 1),)), TypeError, 'typed scalar'),
            (XmlPlan('Text', ('bad',)), TypeError, 'typed scalar'),
            (XmlPlan('Data', children=(Element('Child'),)), TypeError, 'XmlPlan records'),
        )
        for plan, error, message in cases:
            with self.subTest(plan=plan), self.assertRaisesRegex(error, message):
                render_plan(plan, dialect=self.dialect)
        with self.assertRaisesRegex(ValueError, 'newline'):
            render_plan(self.source(), newline='\r')

    def test_shared_immutable_plans_emit_for_each_occurrence_and_depth_is_bounded(self):
        item = XmlPlan('Item', (Value.of('shared'),))
        self.assertEqual(render_plan(XmlPlan('Data', children=(item, item))),
                         '<Data>\n<Item>shared</Item>\n<Item>shared</Item>\n</Data>')
        for _ in range(256):
            item = XmlPlan('Nested', children=(item,))
        with self.assertRaisesRegex(ValueError, 'nesting exceeds 256'):
            render_plan(item)


if __name__ == '__main__':
    unittest.main()
