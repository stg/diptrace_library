"""Verified import defaults become ordinary current design properties."""
import unittest

from lib import ExportReport, new_schematic, parse
from lib.schematic.model.objects import (new_symbol)
from lib.schematic.model.refs import (bind_schematic_references)


class TextImportTests(unittest.TestCase):
    def test_cell_import_removes_only_trailing_blank_rows(self):
        from lib.tests.test_cell_text import table_document
        from lib.common.cell_text import (normalized_cell_text)
        values = ('', ' ', '\n', 'a\n', 'a\n\n', 'a\n ', 'a ', ' a ', 'a\nb\n', 'a\n\t', '\na', 'a\n\r', 'a\n\u00a0')
        expected = ('', '', '', 'a', 'a', 'a', 'a ', ' a ', 'a\nb', 'a\n\t', '\na', 'a\n\r', 'a\n\u00a0')
        source = table_document(rows=tuple(5 for _ in values))
        for cell, text in zip(source.select('/Schematic/Tables/Table/Cells/Cell'), values):
            cell.set_field('Text', text)
        for format in ('dch', 'asc', 'dchxml'):
            current = source
            for cycle in range(3):
                with self.subTest(format=format, cycle=cycle):
                    current = parse(getattr(current, 'to_'+format+'_bytes')(report=ExportReport()), format=format)
                    actual = [cell.scalar('Text') for cell in current.select('/Schematic/Tables/Table/Cells/Cell')]
                    # CR is a restricted ASC string character, independently
                    # reported by that format's existing text sanitizer.
                    wanted = list(expected)
                    if format == 'asc':
                        wanted[-2] = 'a\n!'
                    self.assertEqual(actual, wanted)
        self.assertEqual([cell.scalar('Text') for cell in source.select('/Schematic/Tables/Table/Cells/Cell')], list(values))
        self.assertEqual(tuple(map(normalized_cell_text, values)), expected)

    def test_blank_enabled_field_names_modernize_in_every_input_format(self):
        source = new_schematic()
        part = source.one('/Schematic/Components').append(new_symbol('Device', 'U1'))
        names = ('', ' ', '   ', '\t', ' \t ', ' A ')
        for name in names:
            part.one('UserFields').add('UserField', name, 'value', 0, 0, 7, 0, 0, 0, 0, 0)
        bind_schematic_references(source)
        for format in ('dch', 'asc', 'dchxml'):
            current = source
            for cycle in range(3):
                with self.subTest(format=format, cycle=cycle):
                    current = parse(getattr(current, 'to_'+format+'_bytes')(report=ExportReport()), format=format)
                    self.assertEqual([f.values[0] for f in current.select('/Schematic/Components/Part/UserFields/UserField')],
                                     ['Untitled', 'Untitled', 'Untitled', '\t', ' \t ', ' A '])
        self.assertEqual([f.values[0] for f in part.select('UserFields/UserField')], list(names))

    def test_disabled_component_fields_do_not_receive_the_enabled_field_default(self):
        source = new_schematic()
        part = source.one('/Schematic/Components').append(new_symbol('Device', 'U1'))
        part.set_field('Enabled', False)
        part.one('UserFields').add('UserField', '', 'value', 0, 0, 7, 0, 0, 0, 0, 0)
        bind_schematic_references(source)
        current = parse(source.to_dch_bytes(report=ExportReport()), format='dch')
        self.assertEqual(current.one('/Schematic/Components/Part/UserFields/UserField').values[0], '')


if __name__ == '__main__':
    unittest.main()
