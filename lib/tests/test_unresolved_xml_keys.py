"""Missing public keys cannot silently bind to remapped positional records."""
import unittest
from lib.common.structural_edits import assembly
import xml.etree.ElementTree as ET

from lib import ExportReport, ReferenceError, parse_dch, parse_dchxml
from lib.schematic.model.local_keys import (missing_key)
from lib.tests.test_dimension_selectors import source_document


PATTERN = '/Schematic/CacheLib/Slots/Slot/Definition/Pattern'
PART = '/Schematic/CacheLib/Slots/Slot/Definition/Part'


def source():
    tree = ET.fromstring(source_document(populated=True).to_dchxml_bytes())
    pattern = tree.find('Library/Library/Patterns/Pattern')
    part = tree.find('Library/Components/Component/Part')
    for index, shape in enumerate(pattern.findall('Shapes/Shape'), 2):
        shape.set('Id', str(index*10))
        shape.set('PadId', '1')
    for owner in (part, pattern):
        groups = ET.SubElement(owner, 'Groups')
        for key in (20, 30):
            ET.SubElement(groups, 'Item', Id=str(key), X='0', Y='0')
    pattern.find('Pads/Pad').set('Group', '1')
    pattern.find('Shapes/Shape').set('Group', '20')
    holes = ET.SubElement(pattern, 'Holes')
    for key in (20, 30):
        ET.SubElement(holes, 'Hole', Id=str(key), Group='1', X='0', Y='0', Diam='1')
    attached = pattern.find('Dimensions/Dimension')
    attached.set('Connected1', 'Shape')
    attached.set('SubObject1', '1')
    attached.set('Point1', '-1')
    attached.set('SubObject2', '1')
    attached.set('Group', '1')
    ET.SubElement(pattern.find('Dimensions'), 'Dimension', Connected1='Hole',
                  SubObject1='1', Connected2='-1')
    ET.SubElement(part.find('Pins'), 'Pin', X='0', Y='0', Group='1', PadId='42')
    ET.SubElement(ET.SubElement(part, 'InternalConnections'), 'IntCon', X='1', Y='42')
    return parse_dchxml(ET.tostring(tree)).as_schematic()


def key_facts(document):
    return sorted((node.values[0], node.values[1]) for node in
                  document.select('//UnresolvedKeys/Key'))


class UnresolvedXmlKeyTests(unittest.TestCase):
    def test_missing_keys_survive_repeated_xml_cycles_without_false_targets(self):
        current = source()
        expected = key_facts(current)
        self.assertTrue(expected)
        count = len(current.references.issues)
        for _ in range(3):
            xml = current.as_dchxml(version=48, report=ExportReport())
            for container, kind in (('Pads', 'Pad'), ('Shapes', 'Shape'),
                                     ('Holes', 'Hole'), ('Groups', 'Item')):
                records = xml.select('/Source/Library/Library/Patterns/Pattern/'+container+'/'+kind)
                self.assertNotIn(1, [row.scalar('Id') for row in records])
            self.assertFalse(current.root.changed)
            current = xml.as_schematic()
            self.assertEqual(key_facts(current), expected)
            self.assertEqual(len(current.references.issues), count)
            self.assertEqual(current.one(PATTERN+'/Dimensions/Dimension[1]').scalar('SubObject1'), -1)
            self.assertEqual(current.one(PATTERN+'/InternalConnections/IntCon').values, (-1, 1))

    def test_positional_exports_unassign_missing_targets_only_on_the_export_view(self):
        current = source()
        expected = key_facts(current)
        for kind in ('dch', 'asc'):
            report = ExportReport()
            if kind == 'dch':
                output = parse_dch(current.to_dch_bytes(report=report))
            else:
                output = current.as_asc(report=report).as_schematic()
            self.assertIn('unresolved-local-reference', {notice.rule for notice in report.warnings})
            self.assertEqual(output.one(PATTERN+'/Dimensions/Dimension[1]').scalar('Connected1'), -1)
            self.assertEqual(output.one(PATTERN+'/Dimensions/Dimension[1]').scalar('Connected2'), -1)
            self.assertEqual(output.references.issues, [])
            self.assertEqual(key_facts(current), expected)
            self.assertFalse(current.root.changed)

    def test_related_reordering_is_guarded_while_scalar_edits_remain_available(self):
        current = source()
        current.one(PART).set_field('Value', 'Investigated')
        self.assertEqual(current.as_dchxml(version=48, report=ExportReport()).as_schematic().one(PART).scalar('Value'), 'Investigated')
        groups = current.one(PATTERN+'/Pattern_Groups')
        with self.assertRaisesRegex(ReferenceError, 'unresolved references'):
            groups.children()[0].move_to(groups, 1)
        current.validate()

    def test_invalid_edited_public_key_is_rejected(self):
        current = source()
        shape = current.one(PATTERN+'/Shapes/Shape[2]')
        key = missing_key(shape, 'PadId')
        previous = key['Id']
        with self.assertRaises(TypeError):
            key['Id'] = 'invalid'
        self.assertEqual(key['Id'], previous)

    def test_instantiation_copies_unresolved_pin_groups_as_reference_facts(self):
        current = source()
        tree = ET.fromstring(current.to_dchxml_bytes(version=48, report=ExportReport()))
        style = tree.find('Library/Components/Component').get('ComponentStyle')
        components = tree.find('Schematic/Components')
        if components is None:
            components = ET.SubElement(tree.find('Schematic'), 'Components')
        instance = ET.SubElement(components, 'Part', Id='0', ComponentStyle=style, ComponentPart='0',
                                 Name='Symbol', RefDes='U1', X='0', Y='0', Sheet='0')
        pins = ET.SubElement(instance, 'Pins')
        for _ in tree.findall('Library/Components/Component/Part/Pins/Pin'):
            ET.SubElement(pins, 'Pin', NetId='-1')
        loaded = parse_dchxml(ET.tostring(tree)).as_schematic()
        definition = loaded.one(PART+'/Pins').children('Pin')[-1]
        placed = loaded.one('/Schematic/Components/Part/Pins').children('Pin')[-1]
        self.assertEqual(missing_key(definition, 'Group').values, ('Group', 1))
        self.assertEqual(missing_key(placed, 'Group').values, ('Group', 1))
        self.assertIsNot(missing_key(placed, 'Group'), missing_key(definition, 'Group'))
        self.assertEqual(placed.scalar('Group'), -1)
        again = loaded.as_dchxml(version=48, report=ExportReport()).as_schematic()
        copied = again.one('/Schematic/Components/Part/Pins').children('Pin')[-1]
        self.assertEqual(missing_key(copied, 'Group').values, ('Group', 1))

    def test_unmapped_reference_fields_and_records_are_errors(self):
        for change in ('field', 'record'):
            current = source()
            owner = current.one(PATTERN+'/Shapes/Shape[2]')
            if change == 'field':
                missing_key(owner, 'PadId').set_argument(0, 'UnknownMeaning')
            else:
                # Deliberately construct invalid compatibility data for export.
                with assembly(current):
                    owner.one('UnresolvedKeys').add('UnknownRecord', 42)
            for destination in ('dch', 'asc', 'dchxml'):
                with self.subTest(change=change, destination=destination):
                    with self.assertRaisesRegex(ValueError, 'unsupported unresolved-reference'):
                        getattr(current, 'to_'+destination+'_bytes')(report=ExportReport())


if __name__ == '__main__':
    unittest.main()
