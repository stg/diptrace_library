"""Schematic and PCB XML share the same empty-slot metadata diagnostic policy."""
import unittest
from xml.etree import ElementTree

from lib import ConversionReport, new_schematic, new_symbol, parse, serialize
from lib.common.asc import dumps as model_text
from lib.schematic.formats.capabilities import DCHXML


SLOTS = '/Schematic/CacheLib/Slots'


def document():
    initial = new_schematic()
    initial.one('/Schematic/Components').append(new_symbol('Device', 'U1'))
    return parse(serialize(initial, format='dchxml', report=ConversionReport()), report=ConversionReport())


class SchematicXmlSlotOmissionTests(unittest.TestCase):
    def test_empty_slot_paths_are_reported_in_every_xml_profile(self):
        current = document()
        empty = current.one(SLOTS).add('Slot', 1, 'parts.eli')
        empty['VariablePath'] = 'libraries/parts.eli'
        empty['Model3DFile_Variable'] = 'models/package.step'
        before = model_text(current, preserve=False)
        for version in DCHXML.write_versions:
            with self.subTest(version=version):
                report = ConversionReport()
                output = serialize(current, format='dchxml', version=version, report=report)
                rebuilt = parse(output, report=ConversionReport())
                slots = rebuilt.select(SLOTS+'/Slot')
                self.assertEqual(len(slots), 2)
                self.assertTrue(slots[0].children('Definition'))
                self.assertFalse(slots[1].children('Definition'))
                self.assertEqual(slots[1]['LibPath'], '')
                self.assertEqual(slots[1].get('Model3DFile_Variable', ''), '')
                warnings = [notice for notice in report.warnings if notice.rule in
                            ('empty-library-path', 'unattached-model-path')]
                self.assertEqual({notice.rule for notice in warnings},
                                 {'empty-library-path', 'unattached-model-path'})
                self.assertTrue(all(notice.paths == (empty.path,) for notice in warnings))
                self.assertFalse(report.errors)
                self.assertEqual(model_text(current, preserve=False), before)
                rebuilt.references.validate()

    def test_empty_metadata_does_not_introduce_loss_warnings(self):
        current = document()
        current.one(SLOTS).add('Slot', 1, '')
        report = ConversionReport()
        serialize(current, format='dchxml', report=report)
        self.assertFalse(any(notice.rule in ('empty-library-path', 'unattached-model-path')
                             for notice in report.notices))

    def test_placement_cannot_use_an_empty_component_style(self):
        source = ElementTree.fromstring(serialize(document(), format='dchxml', report=ConversionReport()))
        style = source.find('Library/Components/Component')
        for part in style.findall('Part'):
            style.remove(part)
        with self.assertRaisesRegex(ValueError, 'unresolved component style/variant'):
            parse(ElementTree.tostring(source), report=ConversionReport())


if __name__ == '__main__':
    unittest.main()
