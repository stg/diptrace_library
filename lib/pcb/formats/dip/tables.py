"""Initial PCB table geometry and cell text, before later table extensions."""
from ....common.model import SourceSpan
from ....common.title_block_codec import read_text_content
from .preamble import _fields


def read_base_tables(reader, board):
    tables = board.add('Tables')
    for index in range(reader.count('tables')):
        start = reader.pos
        table = tables.add('Table', index)
        _fields(reader, table, 'boolean', 'Enabled Selected')
        _fields(reader, table, 'integer', 'Layer TextAlign FontSize Orientation Group')
        reader.field(table, 'Color', 'color')
        _fields(reader, table, 'number', 'CellWidth CellHeight X1 Y1 X2 Y2')
        _fields(reader, table, 'text', 'FontName Name')
        widths = table.add('ColWidths')
        columns = reader.count('table columns')
        for _ in range(columns):
            reader.record(widths, 'Item', 'number')
        heights = table.add('RowHeights')
        rows = reader.count('table rows')
        for _ in range(rows):
            reader.record(heights, 'Item', 'number')
        if columns*rows > (len(reader.data)-reader.pos)//42:
            raise reader.error_type(f'table dimensions exceed remaining data at byte {reader.pos:#x}')
        cells = table.add('Cells')
        for column in range(columns):
            for row in range(rows):
                read_text_content(reader, cells.add('Cell', column, row))
        _fields(reader, table, 'boolean', 'Locked VectorFont')
        _fields(reader, table, 'number', 'FontWidth FontScale')
        _fields(reader, table, 'boolean', 'HideBorder PanelExclude')
        if reader.header.version > 32:
            reader.field(table, 'NonSignal', 'integer')
        else:
            table.add('NonSignal', 0)
        table.source = SourceSpan('dip', start, reader.pos, reader.source)
    return tables
