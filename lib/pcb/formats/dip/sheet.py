"""PCB groups and sheet title-block boundary records."""
from ....common.model import SourceSpan
from ....common.title_block_codec import read_title_block
from .preamble import _fields


def read_groups(reader, board):
    groups = reader.add(board, 'Groups')
    for _ in range(reader.count('groups')):
        start = reader.pos
        group = reader.add(groups, 'Group')
        _fields(reader, group, 'boolean', 'Enabled Selected')
        reader.boolean()  # Temporary group state is not carried into the loaded design.
        group.set_values(reader.argument('integer'), reader.argument('number'), reader.argument('number'))
        group.source = SourceSpan('dip', start, reader.pos, reader.source)
    return tuple(groups.children())


def read_sheet_layout(reader, board):
    sheet = reader.add(board, 'SheetSettings')
    _fields(reader, sheet, 'number', 'SheetWidth SheetHeight LeftMargin TopMargin RightMargin BottomMargin')
    titles = reader.add(sheet, 'TitleBlocks')
    for index in range(6):
        read_title_block(reader, titles, index)
    zones = reader.add(sheet, 'BorderZones')
    reader.field_into(zones, 'Visible', 'boolean')
    _fields(reader, zones, 'integer', 'HorzZones VertZones Standard')
    reader.field_into(zones, 'FontName', 'text')
    reader.field_into(zones, 'FontSize', 'integer')
    reader.field_into(zones, 'Border', 'boolean')
    _fields(reader, zones, 'number', 'HorzBorderSize VertBorderSize FontLineWidth')
    return sheet
