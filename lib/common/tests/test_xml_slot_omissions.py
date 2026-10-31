"""Library-slot losses report actual metadata without inventing definitions."""
import unittest

from lib.common.conversion import ConversionReport
from lib.common.model import Document
from lib.common.xml_library_output import report_slot_omissions


class XmlSlotOmissionTests(unittest.TestCase):
    def test_empty_slot_paths_and_unattached_models_have_specific_diagnostics(self):
        document = Document()
        slots = document.root.add('Slots')
        first, second = slots.add('Slot'), slots.add('Slot')
        for node, path in ((first, 'first.eli'), (second, 'second.eli')):
            node.add('LibPath', path)
            node.add('Model3DFile_Variable', 'models/package.step')
        report = ConversionReport()
        report_slot_omissions(slots.children(), destination='dipxml', report=report)
        self.assertEqual({notice.rule for notice in report.warnings},
                         {'empty-library-path', 'unattached-model-path'})
        self.assertTrue(all(notice.paths == (first.path, second.path) for notice in report.warnings))
        self.assertEqual([slot['LibPath'] for slot in slots.children()], ['first.eli', 'second.eli'])
        self.assertTrue(all(not slot.children('Definition') for slot in slots.children()))

    def test_empty_values_and_paths_with_a_definition_are_quiet(self):
        document = Document()
        slots = document.root.add('Slots')
        empty, populated = slots.add('Slot'), slots.add('Slot')
        empty.add('LibPath', '')
        empty.add('VariablePath', '')
        empty.add('Model3DFile_Variable', '')
        populated.add('LibPath', 'parts.eli')
        populated.add('VariablePath', 'libraries/parts.eli')
        populated.add('Definition')
        report = ConversionReport()
        report_slot_omissions(slots.children(), destination='dchxml', report=report)
        self.assertFalse(report.notices)


if __name__ == '__main__':
    unittest.main()
