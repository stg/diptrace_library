"""Binary document sections share styled text and preserve current references."""
from decimal import Decimal, localcontext
from types import SimpleNamespace
import unittest

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.common.font_codec import read_font_properties, write_font_properties
from lib.common.model import Element, Value
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.formats.dip.modern import _board_drawings, _display_extensions
from lib.pcb.formats.dip.project import _table_settings
from lib.pcb.formats.dip.paths import read_column_titles
from lib.pcb.formats.dip.read import Reader
from lib.pcb.formats.dip.sheet import read_sheet_layout
from lib.pcb.formats.dip.settings import (read_display_settings, read_rule_settings,
    read_drc, read_grid_extension)
from lib.pcb.formats.dip.masks import _extend_drc
from lib.pcb.formats.dip.table_model import modernize_tables
from lib.pcb.formats.dip.tables import read_base_tables
from lib.pcb.formats.dip.writer import Writer
from lib.pcb.formats.dip.write_document import (write_sheet_layout, write_base_tables,
    write_document_spacing, write_table_settings, write_table_document_options,
    write_column_titles, document_font_records)
from lib.pcb.formats.dip.write_settings import (write_display_settings, write_rule_settings,
    write_drc, write_mask_settings, write_grid_extension, write_display_extensions)
from lib.pcb.formats.errors import PcbError
from lib.pcb.model import settings_records
from lib.pcb.tests.test_title_relations import design as title_design
from lib.pcb.tests.test_table_model import design as table_design
from lib.pcb.tests.test_table_relations import source as table_source
from lib.pcb.tests.test_table_projection import signature as table_signature
from lib.pcb.tests.test_asc_rules import settings_fixture
from lib.pcb.tests.test_dipxml_design_rules import design as layer_rule_design
from lib.pcb.model.rule_records import DRC_CLEARANCE_NAMES


def sheet_document():
    document = title_design()
    board = document.one('/Board')
    sheet = board.one('SheetSettings')
    for name in ('TopMargin', 'RightMargin', 'BottomMargin'):
        sheet[name] = 0
    zones = sheet.one('BorderZones')
    zones['Standard'], zones['VertBorderSize'] = 0, 0
    board['CompFontMono'] = False
    return document


def sheet_sections(document):
    writer = Writer(report=ConversionReport())
    writer.header()
    write_sheet_layout(writer, document.one('/Board'))
    write_document_spacing(writer, document.one('/Board'))
    write_font_properties(writer, document_font_records(document.one('/Board')))
    return bytes(writer.buffer)


def read_sheet_sections(document):
    data = sheet_sections(document)
    reader, board = Reader(data+b'\0'), Element('Board')
    read_sheet_layout(reader, board)
    _board_drawings(reader, board)
    read_font_properties(reader, document_font_records(board))
    if reader.pos != len(data):
        raise AssertionError('sheet section boundary differs')
    return board


def table_sections(document):
    writer, board = Writer(report=ConversionReport()), document.one('/Board')
    writer.header()
    write_base_tables(writer, board)
    write_document_spacing(writer, board)
    for table in board.select('Tables/Table'):
        write_table_settings(writer, table)
    write_table_document_options(writer, board)
    write_column_titles(writer, board)
    def fonts():
        for table in board.select('Tables/Table'):
            yield table, 'DefFontSize', 'DefFontMono'
            for cell in table.select('Cells/Cell'):
                yield cell, 'FontSize', 'FontMono'
    write_font_properties(writer, fonts())
    for table in board.select('Tables/Table'):
        writer.field(table, 'Supplier', 'text')
    return bytes(writer.buffer)


def read_table_sections(document):
    data = table_sections(document)
    reader, board = Reader(data+b'\0'), Element('Board')
    read_base_tables(reader, board)
    _board_drawings(reader, board)
    for table in board.select('Tables/Table'):
        _table_settings(reader, table)
    for table in board.select('Tables/Table'):
        reader.fields(table, (('DocType','integer'), ('DocUnits','integer')))
    read_column_titles(reader, board)
    def fonts():
        for table in board.select('Tables/Table'):
            yield table, 'FontSize', 'DefFontMono'
            for cell in table.select('Cells/Cell'):
                yield cell, 'FontSize', 'FontMono'
    read_font_properties(reader, fonts())
    for table in board.select('Tables/Table'):
        reader.field(table, 'Supplier', 'text')
    if reader.pos != len(data):
        raise AssertionError('table section boundary differs')
    modernize_tables(SimpleNamespace(board=board, header=reader.header))
    return board


def reopen_tables(document):
    # This existing fixture intentionally has partial footprint data. Supply
    # just the component labels/order needed by the table's positional links;
    # do not run a full component exporter on an unrelated partial fixture.
    source = table_source()
    for old, current in zip(source.select('/Board/Components/Component'), document.select('/Board/Components/Component')):
        old.set_values(current['Name'], Value(current['RefDes'], 'symbol'))
    context = prepare_core(dumps(source, preserve=False))
    for old in tuple(context.board.children('Tables')):
        old.detach()
    read_table_sections(document).one('Tables').move_to(context.board)
    return assemble_graphics(context).document


def settings_document():
    document = assemble_graphics(prepare_core(settings_fixture())).document
    document.root['Units'] = 'mm'
    board = document.one('/Board')
    settings = board.one('Settings')
    for name, field in settings_records.SETTINGS.fields.items():
        if name not in settings:
            settings[name] = False if field.kind == 'boolean' else 0
    for name, value in dict(GridSize=Decimal('.000012345'), GridEnabled=True, YGridSize=Decimal('.6'),
        YGridIdentical=False, AxisColor=0x123456, SilkLineWidth=Decimal('.3'), TableLineWidth=Decimal('.6'),
        TitlesLineWidth=Decimal('.9'), BoardOutlineWidth=Decimal('1.2'), SolderMaskSwell=Decimal('.4'),
        PasteMaskShrink=Decimal('.2')).items():
        settings[name] = value
    sheet = board.add('SheetSettings')
    sheet['DisplayTitles'], sheet['DisplaySheet'] = True, False
    panel = settings.add('LayerPanel')
    for index, name in enumerate(settings_records.LAYER_PANEL.fields):
        panel[name] = index % 2 == 0
    previous = board.one('DRC').clone()
    previous.kind = 'LastDRC'
    board.append(previous)
    return document


def settings_sections(document):
    board, writer = document.one('/Board'), Writer(report=ConversionReport())
    writer.header()
    write_display_settings(writer, document)
    write_rule_settings(writer, board)
    write_drc(writer, board, 'LastDRC')
    write_mask_settings(writer, board)
    write_grid_extension(writer, board)
    write_display_extensions(writer, board)
    return bytes(writer.buffer)


def read_settings_sections(document, *, precision=28):
    data = settings_sections(document)
    reader, board = Reader(data+b'\0'), Element('Board')
    components = board.add('Components')
    for _ in document.select('/Board/Components/Component'):
        components.add('Component')
    display = read_display_settings(reader, board)
    read_rule_settings(reader, board)
    read_drc(reader, board, 'LastDRC')
    reader.fields(board.one('Settings'), (('SolderMaskSwell','number'), ('PasteMaskShrink','number')))
    for kind in ('DRC', 'LastDRC'):
        _extend_drc(reader, board.one(kind))
    with localcontext() as context:
        context.prec = precision
        read_grid_extension(reader, board)
    _display_extensions(reader, board)
    if reader.pos != len(data):
        raise AssertionError('settings section boundary differs')
    return board, display


class DipDocumentOutputTests(unittest.TestCase):
    def test_six_sheet_grids_keep_field_identity_order_text_style_and_bounds(self):
        document = sheet_document()
        grid = document.one('/Board/SheetSettings/TitleBlocks/TitleBlock[1]')
        first = grid.one('Contents/Content[1]')
        first['FontMono'] = True
        first.move_to(first.parent)
        before = dumps(document, preserve=False)
        rebuilt = read_sheet_sections(document)
        self.assertEqual(len(rebuilt.select('SheetSettings/TitleBlocks/TitleBlock')), 6)
        current = rebuilt.one('SheetSettings/TitleBlocks/TitleBlock[1]')
        self.assertEqual([row.values[2] for row in current.select('Cells/Cell')], [1, 0])
        content = current.one('Contents/Content[2]')
        self.assertEqual(content['Text'], 'Revision\nA')
        self.assertEqual(content['FontSize'], Decimal('5.5'))
        self.assertTrue(content['FontMono'])
        self.assertEqual(content.one('Placement').values, (3, -6, 9, -12))
        self.assertEqual(rebuilt.one('SheetSettings')['SheetWidth'], 300)
        self.assertEqual(rebuilt.one('SheetSettings/BorderZones')['FontLineWidth'], Decimal('.6'))
        self.assertEqual(dumps(document, preserve=False), before)
        document.references.validate()

    def test_table_grid_and_generation_settings_do_not_rebuild_current_cells(self):
        document = table_design(table_source())
        table = document.one('/Board/Tables/Table')
        table['Group'] = None
        table['DefFontSize'], table['DefFontMono'] = Decimal('1.125'), True
        cell = table.one('Cells/Cell[1]')
        cell['Text'], cell['FontSize'], cell['FontMono'] = 'Edited Ω\n\nlast line', Decimal('2.125'), True
        table.one('AutoUpdate/Columns/Column')['Title'] = 'Count'
        before, expected = dumps(document, preserve=False), table_signature(table)
        # Mandatory mono bits materialize the declared False default when the
        # optional model field was absent; this is equivalent normalization.
        expected = {name: False if name.endswith('/FontMono') and value is None else value
                    for name, value in expected.items()}
        rebuilt = reopen_tables(document)
        self.assertEqual(table_signature(rebuilt.one(table.path)), expected)
        self.assertEqual(table_signature(reopen_tables(rebuilt).one(table.path)), expected)
        self.assertEqual(dumps(document, preserve=False), before)
        document.references.validate()
        rebuilt.references.validate()

    def test_table_row_component_indices_follow_current_component_order(self):
        document = table_design(table_source())
        first = document.one('/Board/Components/Component[1]')
        first['RefDes'] = 'R8'
        first.move_to(first.parent)
        table = document.one('/Board/Tables/Table')
        table['Group'] = None
        output = read_table_sections(document).one('Tables/Table')
        self.assertEqual(output.one('RowComponents/Row[2]/Item').values, (1,))
        self.assertEqual(reopen_tables(document).one(table.path+'/RowComponents/Row[2]/Item')['Component']['RefDes'], 'R8')

    def test_routing_aliases_settings_fine_grid_and_current_display_records_survive(self):
        document = settings_document()
        routing = document.one('/Board/Settings/Routing')
        routing['TraceWidth'], routing['TraceClearance'] = Decimal('.7498'), Decimal('.3749')
        before = dumps(document, preserve=False)
        board, display = read_settings_sections(document, precision=2)
        self.assertEqual(display.unit_choices, (True, False, False))
        self.assertEqual(board.one('Settings')['GridSize'], Decimal('.000012345'))
        self.assertEqual(board.one('Settings/Routing')['TraceWidth'], Decimal('.7498'))
        self.assertEqual(board.one('Settings/Routing')['TraceClearance'], Decimal('.3749'))
        self.assertEqual(board.one('Settings')['SolderMaskSwell'], Decimal('.4'))
        self.assertEqual(board.one('Settings/LayerPanel')['TopAssy'], True)
        self.assertEqual(board.one('DRC')['CheckKeepouts'], document.one('/Board/DRC').get('CheckKeepouts', False))
        self.assertEqual(board.one('LastDRC')['SilkClearance'], 0)
        self.assertEqual(dumps(document, preserve=False), before)

    def test_unit_switches_follow_the_document_and_unknown_settings_reject(self):
        document = settings_document()
        for units, expected in (('mm',(True,False,False)), ('mil',(False,True,False)), ('inch',(False,False,True))):
            document.root['Units'] = units
            self.assertEqual(read_settings_sections(document)[1].unit_choices, expected)
        document.one('/Board/Settings').add('Unmapped', 10)
        with self.assertRaises(PcbError):
            settings_sections(document)

    def test_missing_mandatory_binary_sheet_data_is_explicit(self):
        document = sheet_document()
        document.remove(document.one('/Board/SheetSettings/TitleBlocks/TitleBlock[6]'))
        with self.assertRaisesRegex(PcbError, 'six title blocks'):
            sheet_sections(document)

    def test_drc_rows_follow_layer_identity_even_when_rule_rows_are_reordered(self):
        document = layer_rule_design().document
        board, writer = document.one('/Board'), Writer(report=ConversionReport())
        drc = board.one('DRC')
        drc.one('LayClearances/LayClearance[3]').move_to(drc.one('LayClearances'), 0)
        drc.one('LaySizes/LaySize[3]').move_to(drc.one('LaySizes'), 0)
        before = dumps(document, preserve=False)
        writer.header()
        write_drc(writer, board)
        reader, target = Reader(bytes(writer.buffer)+b'\0'), Element('Board')
        current = read_drc(reader, target)
        self.assertEqual(reader.pos, len(writer.buffer))
        for layer, row in zip(board.select('Layers/Layer'), current.select('LayClearances/LayClearance')):
            expected = next(source for source in drc.select('LayClearances/LayClearance') if source['Layer'] is layer)
            first, second = expected.one('ClearanceDetails'), row.one('ClearanceDetails')
            for name in DRC_CLEARANCE_NAMES:
                self.assertEqual(second[name], first.get(name, -1))
        for layer, row in zip(board.select('Layers/Layer'), current.select('LaySizes/LaySize')):
            expected = next(source for source in drc.select('LaySizes/LaySize') if source['Layer'] is layer)
            for name in ('MinTrace', 'MinDrill', 'MinRing', 'MaxRing', 'MaxPlatedHole', 'MaxNonPlatedHole'):
                self.assertEqual(row[name], expected.get(name, -1))
        self.assertEqual(dumps(document, preserve=False), before)
        document.references.validate()


if __name__ == '__main__':
    unittest.main()
