"""Standalone component XML reaches the owned model with scoped local identities."""
from copy import deepcopy
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from lib.common.conversion import ConversionReport
from lib.common.errors import UnsupportedFileError
from lib.common.references import ReferenceError
from lib.component.formats.elixml.read import parse
from lib.component.formats.eli.read import parse as parse_binary

FIXTURES = Path(__file__).with_name('fixtures')


def source():
    return ET.fromstring((FIXTURES/'parameters_input.elixml').read_bytes())


def read(root, **options):
    return parse(ET.tostring(root, encoding='utf-8'), **options)


class ComponentXmlReadTests(unittest.TestCase):
    def test_symbol_and_physical_content_share_editable_pad_identities(self):
        document = read(source())
        component = document.one('/Library/Components/Component')
        part = component.one('Parts/Part')
        pattern = component.one('Pattern')
        pads = pattern.select('Pads/Pad')
        pins = part.select('Pins/Pin')
        self.assertEqual(('Example component', 'U', 'Control value'),
                         (component['Name'], component['RefDes'], part['Value']))
        self.assertEqual(2, len(pads))
        self.assertIs(pads[0], pins[0]['Pad'])
        self.assertIs(pads[1], pins[1]['Pad'])
        self.assertIs(pads[1], pattern.one('Shapes/Shape')['Pad'])
        self.assertEqual((3.25, True), (pins[0]['NameFontSize'], pins[0]['NameFontMono']))
        self.assertEqual((7.25, True), tuple(pattern.one('Shapes/Shape')[name] for name in ('FontSize', 'FontMono')))
        self.assertEqual('example.step', pattern.one('Model3D')['Model3DFile'])
        self.assertEqual(1, len(pads[0].children('PadTerminal')))
        pads[1].move_to(pattern.one('Pads'), index=0)
        self.assertEqual((2, 1), tuple(pin['PadId'] for pin in pins))
        self.assertEqual(1, pattern.one('Shapes/Shape')['PadId'])
        document.clone().validate()
        document.validate()

    def test_sparse_public_keys_become_identity_links_in_every_selection(self):
        root = source()
        part = root.find('Components/Component/Part')
        physical = root.find('Library/Patterns/Pattern')
        for key, pad, pin in zip((17, 42), physical.findall('Pads/Pad'), part.findall('Pins/Pin')):
            pad.set('Id', str(key))
            pin.set('PadId', str(key))
        physical.find('Shapes/Shape').set('PadId', '42')
        ET.SubElement(ET.SubElement(part, 'InternalConnections'), 'IntCon', X='42', Y='17')
        ET.SubElement(ET.SubElement(part, 'Groups'), 'Item', Id='9', X='1', Y='2')
        part.find('Pins/Pin').set('Group', '9')
        document = read(root)
        component = document.one('/Library/Components/Component')
        pads = component.select('Pattern/Pads/Pad')
        pair = component.one('Pattern/InternalConnections/IntCon')
        self.assertIs(pads[1], pair['Pad1'])
        self.assertIs(pads[0], pair['Pad2'])
        pin = component.select('Parts/Part/Pins/Pin')[0]
        self.assertIs(pads[0], pin['Pad'])
        self.assertIs(component.one('Parts/Part/Groups/pt'), pin['Group'])
        self.assertEqual((2, 1), pair.values)
        document.validate()

    def test_missing_public_key_never_binds_to_the_same_numbered_internal_slot(self):
        root = source()
        physical = root.find('Library/Patterns/Pattern')
        for pad, key in zip(physical.findall('Pads/Pad'), (17, 42)):
            pad.set('Id', str(key))
        physical.find('Shapes/Shape').set('PadId', '42')
        pins = root.findall('Components/Component/Part/Pins/Pin')
        pins[0].set('PadId', '1')
        pins[1].set('PadId', '42')
        report = ConversionReport()
        document = read(root, report=report)
        component = document.one('/Library/Components/Component')
        pin = component.select('Parts/Part/Pins/Pin')[0]
        self.assertEqual(1, pin['UnresolvedPadId'])
        with self.assertRaises(ReferenceError):
            pin['Pad']
        self.assertTrue(report.warnings)
        self.assertEqual([], report.errors)
        pin['Pad'] = component.select('Pattern/Pads/Pad')[0]
        self.assertIsNone(pin.child('UnresolvedPadId'))
        self.assertEqual([], document.references.issues)
        document.validate()

    def test_missing_dimension_pad_key_never_selects_a_compacted_pad(self):
        root = source()
        physical = root.find('Library/Patterns/Pattern')
        for pad, key in zip(physical.findall('Pads/Pad'), (17, 42)):
            pad.set('Id', str(key))
        physical.find('Shapes/Shape').set('PadId', '42')
        part = root.find('Components/Component/Part')
        for pin, key in zip(part.findall('Pins/Pin'), (17, 42)):
            pin.set('PadId', str(key))
        ET.SubElement(physical.find('Dimensions'), 'Dimension',
                      Connected1='Pad', SubObject1='1', Connected2='None')
        report = ConversionReport()
        document = read(root, report=report)
        dimension = document.one('/Library/Components/Component/Pattern/Dimensions/Dimension')
        self.assertEqual([], document.references.outgoing(dimension, role='pattern-dimension-1'))
        self.assertEqual(1, dimension['SubObject1'])
        self.assertEqual(1, len(document.references.issues))
        self.assertTrue(report.warnings)
        document.clone().validate()
        document.validate()

    def test_zero_selectors_remain_unassigned_even_with_a_zero_public_pad_key(self):
        root = source()
        physical = root.find('Library/Patterns/Pattern')
        physical.find('Pads/Pad').set('Id', '0')
        physical.find('Shapes/Shape').set('PadId', '0')
        part = root.find('Components/Component/Part')
        part.find('Pins/Pin').set('PadId', '0')
        ET.SubElement(ET.SubElement(part, 'InternalConnections'), 'IntCon', X='0', Y='2')
        report = ConversionReport()
        document = read(root, report=report)
        component = document.one('/Library/Components/Component')
        pin = component.select('Parts/Part/Pins/Pin')[0]
        self.assertIsNone(pin['Pad'])
        self.assertEqual(-1, pin['Number'])
        self.assertEqual('1', pin['StringNumber'])
        self.assertIsNone(component.one('Pattern/Shapes/Shape')['Pad'])
        self.assertEqual([], component.select('Pattern/InternalConnections/IntCon'))
        self.assertEqual([], document.references.issues)
        self.assertEqual([], report.warnings)
        self.assertIn('unassigned-internal-connection', [notice.rule for notice in report.notices])

    def test_missing_group_key_does_not_bind_to_its_compacted_position(self):
        root = source()
        part = root.find('Components/Component/Part')
        ET.SubElement(ET.SubElement(part, 'Groups'), 'Item', Id='9', X='1', Y='2')
        part.find('Pins/Pin').set('Group', '0')
        report = ConversionReport()
        document = read(root, report=report)
        component = document.one('/Library/Components/Component')
        pin = component.select('Parts/Part/Pins/Pin')[0]
        self.assertEqual(1, len(report.warnings))
        self.assertEqual(0, pin['UnresolvedGroupId'])
        with self.assertRaises(ReferenceError):
            pin['Group']
        pin['Group'] = component.one('Parts/Part/Groups/pt')
        self.assertEqual([], document.references.issues)
        document.validate()

    def test_components_referencing_one_resource_own_independent_footprints(self):
        root = source()
        collection = root.find('Components')
        other = deepcopy(collection.find('Component'))
        other.find('Part/Name').text = 'Second component'
        collection.append(other)
        document = read(root)
        first, second = document.select('/Library/Components/Component')
        pin = first.select('Parts/Part/Pins/Pin')[0]
        a, b = first.select('Pattern/Pads/Pad')[0], second.select('Pattern/Pads/Pad')[0]
        self.assertIsNot(a, b)
        with self.assertRaises(ReferenceError):
            pin['Pad'] = b
        self.assertIs(a, pin['Pad'])
        a['StringNumber'] = 'Changed'
        self.assertEqual('1', b['StringNumber'])
        document.validate()

    def test_multipart_shared_fields_and_user_data_have_one_owner(self):
        root = source()
        component = root.find('Components/Component')
        first = component.find('Part')
        second = deepcopy(first)
        second.find('Name').text = 'Inactive secondary name'
        second.find('Value').text = 'Second value'
        second.find('PartName').text = 'Gate B'
        component.append(second)
        for part, text in ((first, 'First note'), (second, 'Second note')):
            field = ET.SubElement(ET.SubElement(part, 'AddFields'), 'AddField', Type='Text')
            ET.SubElement(field, 'Name').text = 'Note'
            ET.SubElement(field, 'Text').text = text
        document = read(root)
        component = document.one('/Library/Components/Component')
        self.assertEqual('Example component', component['Name'])
        self.assertEqual(['Control value', 'Second value'], [part['Value'] for part in component.select('Parts/Part')])
        field = component.one('UserFields/UserField')
        self.assertEqual(('Note', 'First note', 0), field.values)
        document.validate()

    def test_empty_input_and_unattached_symbol(self):
        for parts in ('', '<Component><Part><Name>Unattached</Name></Part></Component>'):
            document = parse('<Library Type="DipTrace-ComponentLibrary" Version="5.3.5.1"><Components>'+parts+'</Components></Library>')
            self.assertEqual([], document.select('/Library/Components/Component/Pattern'))
            document.validate()

    def test_zero_assignment_matches_canonical_binary_and_xml(self):
        for parser, name in ((parse, 'zero_input.elixml'), (parse, 'zero_33.elixml'),
                             (parse_binary, 'zero_33.eli')):
            with self.subTest(input=name):
                document = parser((FIXTURES/name).read_bytes(), report=ConversionReport())
                component = document.one('/Library/Components/Component')
                pins = component.select('Parts/Part/Pins/Pin')
                pads = component.select('Pattern/Pads/Pad')
                self.assertIsNone(pins[0]['Pad'])
                self.assertIs(pads[1], pins[1]['Pad'])
                self.assertIsNone(component.one('Pattern/Shapes/Shape')['Pad'])
                self.assertEqual([], component.select('Pattern/InternalConnections/IntCon'))
                self.assertEqual([], document.references.issues)
                document.validate()

    def test_primary_connections_match_canonical_secondary_normalization(self):
        for parser, name in ((parse, 'secondary_connections_input.elixml'),
                             (parse, 'secondary_connections_33.elixml'),
                             (parse_binary, 'secondary_connections_33.eli')):
            with self.subTest(input=name):
                report = ConversionReport()
                document = parser((FIXTURES/name).read_bytes(), report=report)
                component = document.one('/Library/Components/Component')
                self.assertEqual(2, len(component.select('Parts/Part')))
                self.assertEqual([(1, 2)], [row.values for row in component.select('Pattern/InternalConnections/IntCon')])
                self.assertEqual([], document.references.issues)
                self.assertEqual(['secondary-internal-connections'] if name.endswith('_input.elixml') else [],
                                 [notice.rule for notice in report.warnings])
                document.validate()

    def test_unknown_fields_and_unsupported_versions_fail_explicitly(self):
        root = source()
        root.find('Components/Component/Part').set('UnknownSetting', 'Y')
        with self.assertRaises(ValueError):
            read(root)
        root = source()
        root.set('Version', '99.0.0.0')
        with self.assertRaises(UnsupportedFileError) as raised:
            read(root)
        self.assertEqual('version', raised.exception.reason)


if __name__ == '__main__':
    unittest.main()
