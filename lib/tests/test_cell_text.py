"""One current cell text value reaches every public and binary writer."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib import new_schematic, parse_asc, parse_dch, parse_dchxml, DchXmlExportContext, AscExportContext, ExportReport
from lib.schematic.formats.dchxml.import_tables import (read_tables)
from lib.schematic.formats.dchxml.import_values import (XmlRecord)
from lib.common.units import XmlUnits
from lib.schematic.layout.markings import (MarkingStyle)
from lib.schematic.model.refs import (bind_schematic_references)


def table_document(*, columns=(10,), rows=(5,)):
    widths = ''.join(f'<Item>{value}</Item>' for value in columns)
    heights = ''.join(f'<Item>{value}</Item>' for value in rows)
    column = '<Cell>' + '<Cell><TextLines><TextLine>original</TextLine></TextLines></Cell>'*len(rows) + '</Cell>'
    source = parse_dchxml(f'''<Source Type="DipTrace-Schematic"><Schematic><Tables><Table Id="0" Sheet="0">
    <ColWidths>{widths}</ColWidths><RowHeights>{heights}</RowHeights>
    <Cells>{column*len(columns)}</Cells>
    </Table></Tables></Schematic></Source>''')
    result = new_schematic()
    read_tables(XmlRecord(source.one('/Source/Schematic')), result.one('/Schematic'), units=XmlUnits('mm'), sheets={0: 0})
    bind_schematic_references(result)
    for node in result.root.walk(include_self=True):
        node._dirty = node._reordered = False
    return result


class CellTextTests(unittest.TestCase):
    def test_multiline_text_uses_modern_lines_and_legacy_conversion_is_info(self):
        document = table_document()
        document.one('/Schematic/Tables/Table/Cells/Cell').set_field('Text', 'first\nsecond')
        before = document.to_dch_bytes()
        report = ExportReport()
        output = document.as_asc(report=report)
        cell = output.one('/Schematic/Tables/Table/Cells/Cell')
        self.assertEqual(cell.scalar('Text'), 'first!second')
        self.assertEqual(report.warnings, [])
        self.assertEqual([notice.rule for notice in report.infos], ['asc-cell-text-compatibility'])
        imported = output.as_schematic()
        cell = imported.one('/Schematic/Tables/Table/Cells/Cell')
        self.assertEqual(cell.scalar('Text'), 'first\nsecond')
        self.assertIsNone(cell.child('StoredData'))
        self.assertIsNone(cell.child('TextLine'))
        self.assertEqual(imported.to_asc_bytes(report=ExportReport()), output.to_asc_bytes())
        binary = parse_dch(imported.to_dch_bytes())
        self.assertEqual(binary.one('/Schematic/Tables/Table/Cells/Cell').scalar('Text'), 'first\nsecond')
        xml = imported.as_dchxml().as_schematic()
        self.assertEqual(xml.one('/Schematic/Tables/Table/Cells/Cell').scalar('Text'), 'first\nsecond')
        cell.set_field('Text', 'first\nedited')
        changed = imported.as_asc(report=ExportReport()).one('/Schematic/Tables/Table/Cells/Cell')
        self.assertEqual(changed.scalar('Text'), 'first!edited')
        self.assertIsNone(cell.child('StoredData'))
        self.assertEqual(document.to_dch_bytes(), before)

    def test_a_retained_line_with_lost_characters_still_warns(self):
        document = table_document()
        document.one('/Schematic/Tables/Table/Cells/Cell').set_field('Text', 'first "quoted"\nsecond')
        report = ExportReport()
        document.as_asc(report=report)
        notice = next(notice for notice in report.warnings if notice.rule == 'asc-text-sanitization')
        self.assertEqual(len(notice.paths), 1)
        self.assertTrue(notice.paths[0].endswith('/TextLine[1]/pt[1]'))
        self.assertTrue(any(notice.rule == 'asc-cell-text-compatibility' for notice in report.infos))

    def test_distinct_imported_scalar_variant_is_replaced_by_current_lines(self):
        original = table_document().as_asc()
        original.one('/Schematic/Tables/Table/Cells/Cell').set_field('Text', 'legacy-variant')
        shared = original.as_schematic()
        cell = shared.one('/Schematic/Tables/Table/Cells/Cell')
        self.assertEqual(cell.scalar('Text'), 'original')
        self.assertIsNone(cell.child('StoredData'))
        self.assertIsNone(cell.child('TextLine'))
        exported = shared.as_asc().one('/Schematic/Tables/Table/Cells/Cell')
        self.assertEqual(exported.scalar('Text'), 'original')
        self.assertEqual(exported.one('TextLine/pt').values, ('original',))

    def test_asc_table_sizes_have_no_header_count_and_reimport_as_a_grid(self):
        original = table_document(columns=(10, 15), rows=(5, 8))
        before = original.to_dch_bytes()
        current = original
        for _ in range(3):
            output = current.as_asc()
            table = output.one('/Schematic/Tables/Table')
            for name, expected in (('ColWidths', (30, 45)), ('RowHeights', (15, 24))):
                sizes = table.one(name)
                self.assertEqual(sizes.values, ())
                self.assertEqual(tuple(row.values[0] for row in sizes.children('pt')), expected)
            self.assertEqual(table.one('Cells').values, (2,))
            current = parse_asc(output.to_asc_bytes().decode('cp1252')).as_schematic()
            self.assertEqual(len(current.select('/Schematic/Tables/Table/Cells/Cell')), 4)
        self.assertEqual(original.to_dch_bytes(), before)

    def test_text_edits_reach_binary_and_both_public_formats(self):
        for edited in ('edited', 'edited\nsecond'):
            document = table_document()
            cell = document.one('/Schematic/Tables/Table/Cells/Cell')
            cell.set_field('Text', edited)
            data = document.to_dch_bytes()
            self.assertEqual(parse_dch(data).one('/Schematic/Tables/Table/Cells/Cell').scalar('Text'), edited)
            context = DchXmlExportContext(units='mm', grid_snap=True, marking_style=MarkingStyle())
            xml = document.as_dchxml(context=context)
            self.assertEqual([row.values[0] for row in xml.select('/Source/Schematic/Tables/Table/Cells/Cell/Cell/TextLines/TextLine')], edited.split('\n'))
            asc_context = AscExportContext(units='mm', project_dir='', grid_snap=True, marking_style=MarkingStyle())
            asc = document.as_asc(context=asc_context)
            self.assertEqual(asc.one('/Schematic/Tables/Table/Cells/Cell').scalar('Text'), edited.replace('\n', '!'))

    def test_a_second_text_representation_is_rejected_before_output(self):
        document = table_document()
        cell = document.one('/Schematic/Tables/Table/Cells/Cell')
        cell.set_field('Text', 'first')
        cell.add('TextLine').add('pt', 'second')
        with self.assertRaisesRegex(ValueError, 'TextLine is an output view'):
            document.to_dch_bytes()
        with self.assertRaisesRegex(ValueError, 'TextLine is an output view'):
            document.as_dchxml(context=DchXmlExportContext(units='mm', grid_snap=True, marking_style=MarkingStyle()))


if __name__ == '__main__':
    unittest.main()
