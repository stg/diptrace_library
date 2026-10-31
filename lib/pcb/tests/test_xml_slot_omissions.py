"""Known XML slot metadata loss warns while valid definitions remain editable."""
import unittest

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.pcb.formats import io
from lib.pcb.formats.capabilities import FORMATS
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_dipxml_library import source


SLOTS = '/Board/CacheLib/Slots'


class PcbXmlSlotOmissionTests(unittest.TestCase):
    def test_empty_slot_metadata_warns_in_all_xml_profiles_without_changing_source(self):
        document = io.parse(source(), report=ConversionReport())
        empty = document.one(SLOTS).add('Slot', 1, 'parts.eli')
        empty['VariablePath'] = 'libraries/parts.eli'
        empty['Model3DFile_Variable'] = 'models/package.step'
        before = model_text(document, preserve=False)
        for version in FORMATS['dipxml'].write_versions:
            with self.subTest(version=version):
                report = ConversionReport()
                output = io.serialize(document, format='dipxml', version=version, report=report)
                rebuilt = io.parse(output, report=ConversionReport())
                slots = rebuilt.select(SLOTS+'/Slot')
                self.assertEqual(len(slots), 2)
                self.assertTrue(slots[0].children('Definition'))
                self.assertFalse(slots[1].children('Definition'))
                self.assertEqual(slots[1]['LibPath'], '')
                self.assertEqual(slots[1].get('VariablePath', ''), '')
                self.assertEqual(slots[1].get('Model3DFile_Variable', ''), '')
                losses = [notice for notice in report.warnings if notice.rule in
                          ('empty-library-path', 'unattached-model-path')]
                self.assertEqual({notice.rule for notice in losses},
                                 {'empty-library-path', 'unattached-model-path'})
                self.assertTrue(all(notice.paths == (empty.path,) for notice in losses))
                self.assertFalse(report.errors)
                self.assertEqual(model_text(document, preserve=False), before)
                rebuilt.references.validate()

    def test_unknown_slot_data_remains_an_error(self):
        document = io.parse(source(), report=ConversionReport())
        document.one(SLOTS+'/Slot').add('Unmapped', 1)
        before = model_text(document, preserve=False)
        with self.assertRaises(PcbError):
            io.serialize(document, format='dipxml', report=ConversionReport())
        self.assertEqual(model_text(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
