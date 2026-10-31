"""PCB groups and sheet title-block boundary records."""
from ....common.model import SourceSpan
from ....common.title_block_codec import read_title_block
from .preamble import _fields


def read_groups(reader, board):
    groups = board.add('Groups')
    for _ in range(reader.count('groups')):
        start = reader.pos
        group = groups.add('Group')
        _fields(reader, group, 'boolean', 'Enabled Selected')
        reader.boolean()  # Temporary group state is not carried into the loaded design.
        group.set_values(reader.argument('integer'), reader.argument('number'), reader.argument('number'))
        group.source = SourceSpan('dip', start, reader.pos, reader.source)
    return tuple(groups.children())


def read_sheet_layout(reader, board):
    sheet = board.add('SheetSettings')
    _fields(reader, sheet, 'number', 'SheetWidth SheetHeight LeftMargin TopMargin RightMargin BottomMargin')
    titles = sheet.add('TitleBlocks')
    for index in range(6):
        read_title_block(reader, titles, index)
    zones = sheet.add('BorderZones')
    reader.field(zones, 'Visible', 'boolean')
    _fields(reader, zones, 'integer', 'HorzZones VertZones Standard')
    reader.field(zones, 'FontName', 'text')
    reader.field(zones, 'FontSize', 'integer')
    reader.field(zones, 'Border', 'boolean')
    _fields(reader, zones, 'number', 'HorzBorderSize VertBorderSize FontLineWidth')
    return sheet
