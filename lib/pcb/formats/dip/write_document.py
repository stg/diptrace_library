"""Binary sheet, title and table sections over the shared editable records.

These section functions require complete current data for mandatory slots.
The document composer owns defaults for optional input sections and context.
"""
from ....common.title_block_codec import write_title_block, write_text_content
from ...model import settings_records, table_records, graphic_records
from ..errors import PcbError
from ..output_indices import non_signal_number
from ..output_validation import check_tree


def write_sheet_layout(writer, board):
    sheet = board.child('SheetSettings')
    if sheet is None:
        raise PcbError(f'{board.path}: sheet settings are needed for binary output')
    check_tree(sheet, settings_records.SHEET, destination='DIP')
    writer.fields(sheet, 'number', 'SheetWidth SheetHeight LeftMargin TopMargin RightMargin BottomMargin')
    titles = sheet.select('TitleBlocks/TitleBlock')
    if len(titles) != 6:
        raise PcbError(f'{sheet.path}: binary sheet output requires six title blocks')
    for title in titles:
        write_title_block(writer, title)
    zones = sheet.child('BorderZones')
    if zones is None:
        raise PcbError(f'{sheet.path}: border-zone settings are needed for binary output')
    writer.field(zones, 'Visible', 'boolean')
    writer.fields(zones, 'integer', 'HorzZones VertZones Standard')
    writer.field(zones, 'FontName', 'text')
    writer.field(zones, 'FontSize', 'integer')
    writer.field(zones, 'Border', 'boolean')
    writer.fields(zones, 'number', 'HorzBorderSize VertBorderSize FontLineWidth')


def write_base_tables(writer, board):
    source = board.child('Tables')
    if source is not None:
        check_tree(source, graphic_records.COLLECTIONS['Tables'], destination='DIP')
    tables = board.select('Tables/Table')
    writer.integer(len(tables))
    for table in tables:
        check_tree(table, table_records.TABLE, destination='DIP')
        writer.fields(table, 'boolean', 'Enabled Selected')
        writer.fields(table, 'integer', 'Layer DefAlign DefFontSize Orientation Group')
        writer.field(table, 'DefFontColor', 'color')
        writer.fields(table, 'number', 'DefCellWidth DefCellHeight X1 Y1 X2 Y2')
        writer.fields(table, 'text', 'DefFontName Name')
        writer.rows(table.one('ColWidths'), 'pt', 'number')
        writer.rows(table.one('RowHeights'), 'pt', 'number')
        cells = table.select('Cells/Cell')
        if len(cells) != len(table.select('ColWidths/pt'))*len(table.select('RowHeights/pt')):
            raise PcbError(f'{table.path}: table cells do not form a rectangle')
        for cell in cells:
            write_text_content(writer, cell)
        writer.fields(table, 'boolean', 'Locked DefVectorFont')
        writer.fields(table, 'number', 'DefFontWidth DefFontScale')
        writer.fields(table, 'boolean', 'HideBorder PanelExclude')
        writer.integer(non_signal_number(table, destination='dip', report=writer.report))


def write_document_spacing(writer, board):
    """Current line spacing follows the board-drawing extension records."""
    for table in board.select('Tables/Table'):
        writer.field(table, 'DefLineSpacing', 'number')
        for cell in table.select('Cells/Cell'):
            writer.field(cell, 'LineSpacing', 'number')
    for title in board.select('SheetSettings/TitleBlocks/TitleBlock'):
        for content in title.select('Contents/Content'):
            writer.field(content, 'LineSpacing', 'number')


def write_table_settings(writer, table):
    """Saved regeneration settings and row membership, without rebuilding cells."""
    rows = table.select('RowComponents/Row')
    writer.integer(len(rows))
    for row in rows:
        members = row.children('Item')
        writer.integer(len(members))
        for member in members:
            writer.field(member, 'ComponentIndex', 'integer')
    update = table.one('AutoUpdate')
    writer.fields(update, 'integer', 'AssemblyVariant RowType')
    writer.fields(update, 'number', 'PickOffX PickOffY')
    writer.fields(update, 'boolean', 'Header BomRowNumber BomTotal PickMirror PickOrigin')
    writer.fields(update, 'text', 'AssemblyName Separator')
    columns = update.select('Columns/Column')
    writer.integer(len(columns))
    for column in columns:
        writer.fields(column, 'integer', 'Type TextAlign')
        writer.field(column, 'Width', 'number')
        writer.field(column, 'Name', 'text')


def write_table_document_options(writer, board):
    for table in board.select('Tables/Table'):
        writer.fields(table, 'integer', 'DocType DocUnits')


def write_column_titles(writer, board):
    for column in board.select('Tables/Table/AutoUpdate/Columns/Column'):
        writer.scalar(column, 'Title', 'text', default='')


def document_font_records(board):
    """The current table/zone/title font extension order."""
    for table in board.select('Tables/Table'):
        yield table, 'DefFontSize', 'DefFontMono'
        for cell in table.select('Cells/Cell'):
            yield cell, 'FontSize', 'FontMono'
    yield board, 'CompFontSize', 'CompFontMono'
    yield board.one('SheetSettings/BorderZones'), 'FontSize', None
    for title in board.select('SheetSettings/TitleBlocks/TitleBlock'):
        for content in title.select('Contents/Content'):
            yield content, 'FontSize', 'FontMono'
