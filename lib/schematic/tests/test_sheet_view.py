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

    def test_binary_selection_survives_versions_and_xml_conversion(self):
        doc = self.design()
        for version in range(46, 53):
            with self.subTest(version=version):
                report = ConversionReport()
                raw = serialize(doc, format='dch', version=version, report=report)
                restored = parse(raw)
                self.assertEqual(restored.one('/Schematic')['ActiveSheet'], 1)
                self.assertNotIn('PictureCount', restored.one('/Schematic'))
                self.assertFalse(any(n.rule == 'active-sheet' for n in report.notices))
                self.assertEqual(serialize(restored, format='dch', version=version), raw)
                xml = parse(serialize(restored, format='dchxml'))
                page = xml.one('/Schematic/Pages/Page[Name="Second"]')
                page.move_to(page.parent, 0)
                rebuilt = parse(serialize(xml, format='dch', version=version))
                self.assertEqual(rebuilt.one('/Schematic')['ActiveSheet'], 0)
                self.assertEqual(rebuilt.one('/Schematic/Pages').children('Page')[0]['Name'],
                                 'Second')
                self.assertEqual(doc.one('/Schematic')['ActiveSheet'], 1)

    def test_asc_reports_selection_omission_without_mutation(self):
        doc = self.design()
        report = ConversionReport()
        restored = parse(serialize(doc, format='asc', report=report))
        self.assertNotIn('ActiveSheet', restored.one('/Schematic'))
        self.assertNotIn('PictureCount', restored.one('/Schematic'))
        self.assertEqual(doc.one('/Schematic')['ActiveSheet'], 1)
        notices = [notice for notice in report.notices if notice.rule == 'active-sheet']
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0].severity, 'info')

    def test_absent_selection_uses_first_sheet_on_binary_output(self):
        doc = new_schematic()
        schematic = doc.one('/Schematic')
        if 'ActiveSheet' in schematic:
            del schematic['ActiveSheet']
        restored = parse(serialize(doc, format='dch'))
        self.assertEqual(restored.one('/Schematic')['ActiveSheet'], 0)
        self.assertNotIn('ActiveSheet', schematic)

    def test_selection_can_be_removed_and_invalid_positions_remain_explicit(self):
        doc = self.design()
        schematic = doc.one('/Schematic')
        for reference in doc.references.outgoing(schematic.child('ActiveSheet')):
            doc.references.discard(reference)
        del schematic['ActiveSheet']
        self.assertEqual(DchXmlExportContext().resolved(doc).active_sheet, 0)
        schematic['ActiveSheet'] = 9
        self.assertTrue(any(issue.message.startswith('active-sheet:') for issue in doc.references.issues))
        for kind in ('dch', 'dchxml'):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                serialize(doc, format=kind, report=ConversionReport())
