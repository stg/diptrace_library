"""Sheet selection is model data, with an optional detached export override."""
import unittest

from lib import (ConversionReport, DchXmlExportContext, ReferenceError,
                        new_schematic, parse, parse_dchxml, serialize)
from lib.schematic.model.new import new_page


class SheetViewTests(unittest.TestCase):
    def design(self):
        doc = new_schematic()
        pages = doc.one('/Schematic/Pages')
        pages.append(new_page('Second'))
        doc.one('/Schematic')['ActiveSheet'] = 1
        return doc

    def test_selection_survives_xml_import_reorder_and_export(self):
        source = self.design()
        doc = parse(serialize(source, format='dchxml'), format='dchxml')
        schematic = doc.one('/Schematic')
        self.assertEqual(schematic['ActiveSheet'], 1)
        self.assertNotIn('active_sheet', doc.metadata)
        page = doc.one('/Schematic/Pages/Page[Name="Second"]')
        page.move_to(page.parent, 0)
        self.assertEqual(schematic['ActiveSheet'], 0)
        output = parse_dchxml(serialize(doc, format='dchxml'))
        self.assertEqual(output.one('/Source/Schematic/SheetSettings')['ActiveSheet'], 0)
        with self.assertRaises(ReferenceError):
            doc.remove(page)

    def test_override_and_resolved_defaults_do_not_change_selection(self):
        doc = self.design()
        self.assertEqual(DchXmlExportContext().resolved(doc).active_sheet, 1)
        output = parse_dchxml(serialize(doc, format='dchxml',
                                      context=DchXmlExportContext(active_sheet=0)))
        self.assertEqual(output.one('/Source/Schematic/SheetSettings')['ActiveSheet'], 0)
        self.assertEqual(doc.one('/Schematic')['ActiveSheet'], 1)
        cloned = doc.clone()
        cloned.one('/Schematic/Pages/Page[Name="Second"]').move_to(cloned.one('/Schematic/Pages'), 0)
        self.assertEqual(cloned.one('/Schematic')['ActiveSheet'], 0)
        self.assertEqual(doc.one('/Schematic')['ActiveSheet'], 1)

    def test_record_destinations_report_selection_omission_without_mutation(self):
        doc = self.design()
        for kind in ('dch', 'asc'):
            with self.subTest(kind=kind):
                report = ConversionReport()
                restored = parse(serialize(doc, format=kind, report=report), format=kind)
                self.assertNotIn('ActiveSheet', restored.one('/Schematic'))
                self.assertEqual(doc.one('/Schematic')['ActiveSheet'], 1)
                notices = [notice for notice in report.notices if notice.rule == 'active-sheet']
                self.assertEqual(len(notices), 1)
                self.assertEqual(notices[0].severity, 'info')

    def test_selection_can_be_removed_and_invalid_positions_remain_explicit(self):
        doc = self.design()
        schematic = doc.one('/Schematic')
        for reference in doc.references.outgoing(schematic.child('ActiveSheet')):
            doc.references.discard(reference)
        del schematic['ActiveSheet']
        self.assertEqual(DchXmlExportContext().resolved(doc).active_sheet, 0)
        schematic['ActiveSheet'] = 9
        self.assertTrue(any(issue.message.startswith('active-sheet:') for issue in doc.references.issues))
        with self.assertRaises(ValueError):
            serialize(doc, format='dchxml', report=ConversionReport())
