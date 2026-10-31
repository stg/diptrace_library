"""Whole embedded-library output preserves ownership, keys and current edits."""
from decimal import Decimal
import unittest
from xml.etree import ElementTree

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.common.model import Document
from lib.common.units import XmlUnits
from lib.common.xml import set_attribute
from lib.pcb.formats.dipxml.library_output import project_library
from lib.pcb.formats.dipxml.syntax import dumps
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_cache_projection import signature
from lib.pcb.tests.test_dipxml_library import read, source


SLOT = '/Board/CacheLib/Slots/Slot'


def reopen(document, *, units='mm', report=None):
    projected = project_library(document.one('/Board'), units=XmlUnits(units), report=report)
    wrapper = Document(representation='xml')
    root = wrapper.root.add('Source')
    for name, value in (('Type', 'DipTrace-PCB'), ('Version', '5.3.5.1'), ('Units', units)):
        set_attribute(root, name, value)
    root.append(projected.element)
    board = root.add('Board')
    layers = board.add('CopperLayers')
    for index, name in enumerate(('Top', 'Bottom')):
        layer = layers.add('Lay')
        set_attribute(layer, 'Id', index)
        layer.add('Name', name)
    board.add('Components')
    board.add('Nets')
    return read(dumps(wrapper), report=ConversionReport()), projected


class XmlLibraryOutputTests(unittest.TestCase):
    def test_template_fields_remain_independent_of_symbol_fields_and_style_sharing(self):
        for field, value in (('Name', 'Alternative names'), ('Value', 'Other package'), ('Type', 1)):
            with self.subTest(field=field):
                document = read(source(components=2), report=ConversionReport())
                for definition in document.select(SLOT+'/Definition'):
                    # A component definition and its reusable physical template
                    # can carry different fields, even when geometry is shared.
                    definition.one('Part/UserFields').add('UserField', 'Datasheet',
                        'https://example.invalid/datasheet.pdf', 1, *(0 for _ in range(7)))
                    definition.one('Pattern/UserFields').add('UserField', 'Package names', 'Package', 0)
                document.one(SLOT+'[2]/Definition/Pattern/UserFields/UserField')[field] = value
                expected = signature(document.one('/Board/CacheLib'))
                for _ in range(2):
                    before = model_text(document, preserve=False)
                    rebuilt, projected = reopen(document, report=ConversionReport())
                    self.assertEqual(len(projected.element.select('Library/Patterns/Pattern')), 2)
                    self.assertEqual(signature(rebuilt.one('/Board/CacheLib')), expected)
                    self.assertEqual(model_text(document, preserve=False), before)
                    rebuilt.references.validate()
                    document = rebuilt

    def test_display_and_generation_settings_keep_physical_styles_distinct(self):
        # Identical geometry does not make these independent template settings
        # interchangeable. Each setting must participate in style sharing.
        for path, field, value in (('', 'OriginCross', False),
                                   ('', 'OriginCircle', False),
                                   ('', 'OriginCommon', 0),
                                   ('', 'OriginCourtyard', 1),
                                   ('Model3D', 'AutoColor', 0x336699)):
            with self.subTest(field=field):
                document = read(source(components=2), report=ConversionReport())
                second = document.one(SLOT+'[2]/Definition/Pattern')
                owner = second.one(path) if path else second
                owner[field] = value
                expected = signature(document.one('/Board/CacheLib'))
                for _ in range(2):
                    before = model_text(document, preserve=False)
                    rebuilt, projected = reopen(document, report=ConversionReport())
                    self.assertEqual(len(projected.element.select('Library/Patterns/Pattern')), 2)
                    self.assertEqual(signature(rebuilt.one('/Board/CacheLib')), expected)
                    self.assertEqual(model_text(document, preserve=False), before)
                    rebuilt.references.validate()
                    document = rebuilt

    def test_empty_physical_template_retains_display_and_model_settings(self):
        root = ElementTree.fromstring(source())
        pattern = root.find('Library/Library/Patterns/Pattern')
        pattern.find('Name').text = ''
        for name in ('Pads', 'Shapes', 'Holes'):
            if (collection := pattern.find(name)) is not None:
                collection.clear()
        part = root.find('Library/Components/Component/Part')
        part.find('Pins').clear()
        part.find('InternalConnections').clear()
        root.find('Board/Components').clear()
        root.find('Board/Nets').clear()
        document = read(ElementTree.tostring(root), report=ConversionReport())
        pattern = document.one(SLOT+'/Definition/Pattern')
        for name, value in dict(OriginCross=True, OriginCircle=True,
                                OriginCommon=1, OriginCourtyard=2).items():
            pattern[name] = value
        pattern.one('Model3D')['AutoColor'] = 0x336699
        expected = signature(document.one('/Board/CacheLib'))
        for _ in range(2):
            before = model_text(document, preserve=False)
            rebuilt, projected = reopen(document, report=ConversionReport())
            physical = projected.element.one('Library/Patterns/Pattern')
            self.assertEqual((physical.one('Origin')['Cross'], physical.one('Origin')['Common']), (True, 'Hide'))
            self.assertEqual(physical.one('Model3D')['AutoColor'], 0x336699)
            self.assertEqual(signature(rebuilt.one('/Board/CacheLib')), expected)
            self.assertEqual(model_text(document, preserve=False), before)
            rebuilt.references.validate()
            document = rebuilt

    def test_distinct_cached_components_share_only_the_generated_physical_style(self):
        document = read(source(components=2), report=ConversionReport())
        cache = document.one('/Board/CacheLib')
        before = model_text(document, preserve=False)
        rebuilt, projected = reopen(document, report=ConversionReport())
        self.assertEqual(len(projected.element.select('Components/Component')), 2)
        self.assertEqual(len(projected.element.select('Library/Patterns/Pattern')), 1)
        self.assertEqual(signature(rebuilt.one('/Board/CacheLib')), signature(cache))
        first, second = rebuilt.select(SLOT)
        first.one('Definition/Pattern/Pads/Pad[1]')['X'] = 99
        self.assertEqual(second.one('Definition/Pattern/Pads/Pad[1]')['X'], 3)
        self.assertEqual(model_text(document, preserve=False), before)

    def test_multipart_missing_pattern_and_edited_pad_order_preserve_assignments(self):
        root = ElementTree.fromstring(source())
        component = root.find('Library/Components/Component')
        secondary = ElementTree.fromstring(ElementTree.tostring(component.find('Part')))
        secondary.find('Name').text = 'Second section'
        secondary.find('Pins/Pin').set('PadId', '41')
        secondary.remove(secondary.find('Pattern'))
        secondary.find('InternalConnections').clear()
        component.append(secondary)
        document = read(ElementTree.tostring(root, encoding='unicode'), report=ConversionReport())
        pattern = document.one(SLOT+'/Definition[1]/Pattern')
        pattern.one('Pads/Pad[2]').move_to(pattern.one('Pads'), 0)
        expected = signature(document.one(SLOT))
        for _ in range(3):
            document, _ = reopen(document, report=ConversionReport())
            self.assertEqual(signature(document.one(SLOT)), expected)
            second = document.one(SLOT+'/Definition[2]/Part')
            target = document.references.outgoing(second, role='symbol-pin-pad')[0].target
            self.assertEqual(target['Id'], 41)
            self.assertEqual(second.one('Pins/Pin')['Number'], 1)
            document.references.validate()

    def test_independent_equal_patterns_and_named_pad_styles_are_not_absorbed(self):
        root = ElementTree.fromstring(source())
        library = root.find('Library/Library')
        styles, patterns = library.find('PadStyles'), library.find('Patterns')
        for name in ('Pad1', 'Pad0'):
            style = ElementTree.fromstring(ElementTree.tostring(styles.find('PadStyle')))
            style.set('Name', name)
            styles.append(style)
        for name in ('UnusedA', 'UnusedB'):
            pattern = ElementTree.fromstring(ElementTree.tostring(patterns.find('Pattern')))
            pattern.set('PatternStyle', name)
            patterns.append(pattern)
        document = read(ElementTree.tostring(root, encoding='unicode'), report=ConversionReport())
        # A distinct style choice is meaningful even when its geometry happens
        # to equal this pattern's default pad style.
        document.one(SLOT+'/Definition/Pattern/Pads/Pad[1]')['Standard'] = False
        expected = signature(document.one('/Board/CacheLib'))
        rebuilt, projected = reopen(document, report=ConversionReport())
        self.assertEqual(signature(rebuilt.one('/Board/CacheLib')), expected)
        self.assertEqual(len(rebuilt.select('/Board/CacheLib/Patterns/Pattern')), 2)
        self.assertEqual([style['Name'] for style in rebuilt.select('/Board/CacheLib/PadStyles/PadStyle')], ['Pad1', 'Pad0'])
        self.assertEqual(len(projected.element.select('Library/Patterns/Pattern')), 3)
        self.assertFalse(rebuilt.one(SLOT+'/Definition/Pattern/Pads/Pad[1]')['Standard'])
        self.assertEqual(signature(reopen(rebuilt, report=ConversionReport())[0].one('/Board/CacheLib')), expected)

    def test_units_catalogs_and_explicit_blank_variable_paths_survive(self):
        document = read(source(), report=ConversionReport())
        slot = document.one(SLOT)
        slot['VariablePath'] = ''
        part = slot.one('Definition/Part')
        part.one('Pins/Pin')['NameFontSize'] = Decimal('6.25')
        expected = signature(document.one('/Board/CacheLib'))
        for units in ('mm', 'mil', 'inch'):
            with self.subTest(units=units):
                rebuilt, _ = reopen(document, units=units, report=ConversionReport())
                actual = signature(rebuilt.one('/Board/CacheLib'))
                self.assertEqual(actual.keys(), expected.keys())
                for path, value in expected.items():
                    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
                        self.assertLessEqual(abs(Decimal(str(actual[path]))-Decimal(str(value))), Decimal('1e-28'), path)
                    else:
                        self.assertEqual(actual[path], value, path)
                self.assertEqual(rebuilt.one(SLOT)['VariablePath'], '')

    def test_empty_component_slots_remain_empty_without_synthetic_symbols(self):
        document = read(source(), report=ConversionReport())
        document.one('/Board/CacheLib/Slots').add('Slot', 1, '')
        report = ConversionReport()
        rebuilt, projected = reopen(document, report=report)
        self.assertFalse(projected.element.one('Components/Component[2]').children('Part'))
        self.assertFalse(rebuilt.one(SLOT+'[2]').children('Definition'))
        self.assertTrue(any(notice.rule == 'library-cache-selection' and notice.severity == 'info' for notice in report.notices))

    def test_bound_targets_outside_primary_domain_fail_without_changing_source(self):
        document = read(source(), report=ConversionReport())
        definition = document.one(SLOT+'/Definition')
        duplicate = document.copy(definition, parent=definition.parent)
        # Copying remaps this section's pin to its newly copied pad identity.
        # XML's single primary electrical domain cannot encode that assignment.
        self.assertIs(document.references.outgoing(duplicate.one('Part'), role='symbol-pin-pad')[0].target.parent.parent,
                      duplicate.one('Pattern'))
        before = model_text(document, preserve=False)
        with self.assertRaisesRegex(PcbError, 'no physical XML key'):
            project_library(document.one('/Board'), units=XmlUnits('mm'), report=ConversionReport())
        self.assertEqual(model_text(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
