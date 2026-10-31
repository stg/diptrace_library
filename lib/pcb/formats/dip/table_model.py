"""Current table fields from binary grid headers, without generated snapshots."""
from decimal import Decimal

from ....common.cell_text import modernize_cell_text
from ..errors import PcbError


DEFAULT_NAMES = {
    'VectorFont': 'DefVectorFont', 'TextAlign': 'DefAlign', 'FontSize': 'DefFontSize',
    'Color': 'DefFontColor', 'CellWidth': 'DefCellWidth', 'CellHeight': 'DefCellHeight',
    'FontName': 'DefFontName', 'FontWidth': 'DefFontWidth', 'FontScale': 'DefFontScale',
}


def _defaults(owner, values):
    for name, value in values.items():
        if owner.child(name) is None:
            owner.add(name, value)


def modernize_tables(decoded):
    board = decoded.board
    for table in board.select('Tables/Table'):
        for old, current in DEFAULT_NAMES.items():
            if (field := table.child(old)) is not None:
                if table.child(current) is not None:
                    raise PcbError(f'{table.path}: conflicting table default {current}')
                field.kind = current
        if decoded.header.version < 47:
            table.add('DefLineSpacing', Decimal('1.2'))
        if decoded.header.version < 43:
            _defaults(table, dict(DocType=0, DocUnits=0))
        if decoded.header.version < 50:
            if table.child('RowComponents') is None:
                table.add('RowComponents')
            update = table.child('AutoUpdate')
            if update is None:
                update = table.add('AutoUpdate')
            _defaults(update, dict(AssemblyVariant=0, RowType=0, PickOffX=0, PickOffY=0,
                Header=False, BomRowNumber=False, BomTotal=False, PickMirror=False,
                PickOrigin=False, AssemblyName='', Separator='.'))
            if update.child('Columns') is None:
                update.add('Columns')
        if decoded.header.version < 52:
            _defaults(table, dict(Supplier=''))
        widths, heights = table.one('ColWidths'), table.one('RowHeights')
        for collection in (widths, heights):
            for row in collection.children():
                row.kind = 'pt'
        columns, rows = len(widths.children()), len(heights.children())
        cells = table.one('Cells').children()
        if len(cells) != columns*rows:
            raise PcbError(f'{table.path}: table cells do not form a rectangle')
        for index, cell in enumerate(cells):
            if cell.values != (index//rows, index % rows):
                raise PcbError(f'{cell.path}: invalid binary cell position')
            placement = cell.one('Placement')
            if len(placement.arguments) != 4:
                raise PcbError(f'{cell.path}: invalid cell bounds')
            cell.set_values(*placement.arguments)
            placement.detach()
            if decoded.header.version < 47:
                cell.add('LineSpacing', Decimal('1.2'))
    modernize_cell_text(board, paths=('Tables/Table/Cells/Cell',))
