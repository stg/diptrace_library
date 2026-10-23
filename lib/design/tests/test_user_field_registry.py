"""Explicit registry refresh projects data without replacing source choices."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lib.design import new_schematic, AscExportContext, DchXmlExportContext, ExportReport, parse_dch
from lib.design.schematic_objects import new_symbol
from lib.design.schematic_refs import bind_schematic_references
from lib.design.user_fields import global_user_field_registry


class UserFieldRegistryTests(unittest.TestCase):
    def source(self):
        document = new_schematic()
        part = document.one('/Schematic/Components').append(new_symbol('Block', 'U1'))
        for name in ('Rating', 'R ATING', ''):
            part.one('UserFields').add('UserField', name, '', *(0 for _ in range(8)))
        choices = document.one('/Schematic/ShowUserfield_Global')
        choices.add('pt', 'Unused', 'unused', 1, 3)
        choices.add('pt', 'Saved spelling', 'rating', 1, 5)
        bind_schematic_references(document)
        return document

    def test_first_use_names_and_existing_choices_have_separate_roles(self):
        source = self.source()
        schematic = source.one('/Schematic')
        rows = global_user_field_registry(schematic.select('Components/Part'),
                                         [row.values for row in schematic.select('ShowUserfield_Global/pt')])
        self.assertEqual(rows, (('Rating', 'rating', 1, 5), ('Untitled', 'untitled', 2, 7)))

    def test_refresh_is_optional_and_only_changes_export_views(self):
        source = self.source()
        before = [row.values for row in source.select('/Schematic/ShowUserfield_Global/pt')]
        self.assertEqual([row.values for row in source.as_asc().select('/Schematic/ShowUserfield_Global/pt')], before)
        report = ExportReport()
        output = source.as_asc(context=AscExportContext(refresh_user_fields=True), report=report)
        self.assertEqual([row.values for row in output.select('/Schematic/ShowUserfield_Global/pt')],
                         [('Rating', 'rating', 1, 5), ('Untitled', 'untitled', 2, 7)])
        self.assertIn('global-user-field-choices', {notice.rule for notice in report.infos})
        self.assertEqual([row.values for row in source.select('/Schematic/ShowUserfield_Global/pt')], before)

    def test_the_same_refresh_option_applies_to_binary_and_xml_exports(self):
        source = self.source()
        report = ExportReport()
        binary = parse_dch(source.to_dch_bytes(context=AscExportContext(refresh_user_fields=True), report=report))
        self.assertEqual([row.values for row in binary.select('/Schematic/ShowUserfield_Global/pt')],
                         [('Rating', 'rating', 1, 5), ('Untitled', 'untitled', 2, 7)])
        xml = source.as_dchxml(context=DchXmlExportContext(refresh_user_fields=True), report=report)
        self.assertTrue(xml.complete)
        self.assertEqual([row.values for row in source.select('/Schematic/ShowUserfield_Global/pt')],
                         [('Unused', 'unused', 1, 3), ('Saved spelling', 'rating', 1, 5)])


if __name__ == '__main__':
    unittest.main()
