"""Detached PCB ASC table views over current cells and component identities.

Counts and positions are calculated from current ownership. The document
writer combines this section with its other output projections.
"""
from ....common import cell_records
from ....common.cell_text import asc_cell_text, cell_lines
from ....common.conversion import warn
from ....common.model import Element
from ...model import table_records as model
from ...model import graphic_records
from ..errors import PcbError
from .projection import check as _check
from .projection import collection, non_signal_number
from .table_settings import SETTINGS


def _add(output, name, value):
    output.add(name, ('Y' if value else 'N') if isinstance(value, bool) else value)


def _cells(table, output):
    columns, rows = [], []
    for name, schema, value_name, sizes in (
            ('ColWidths', cell_records.COLUMN_WIDTH, 'Width', columns),
            ('RowHeights', cell_records.ROW_HEIGHT, 'Height', rows)):
        collection = table.one(name)
        _check(collection, cell_records.COLUMN_WIDTHS if name == 'ColWidths' else cell_records.ROW_HEIGHTS)
        projected = output.add(name)
        for size in collection.children():
            _check(size, schema)
            sizes.append(size[value_name])
            projected.add('pt', size[value_name])
    cells = table.one('Cells')
    _check(cells, cell_records.CELLS)
    if len(cells.children()) != len(columns)*len(rows):
        raise PcbError(f'{cells.path}: cells do not form the declared table rectangle')
    projected = output.add('Cells', len(columns))
    for index, cell in enumerate(cells.children()):
        _check(cell, cell_records.CELL)
        column, row = divmod(index, len(rows))
        record = projected.add('Cell', len(rows), column, row, *cell.values)
        for name, field in cell_records.CELL.fields.items():
            if field.getter is None and name not in (*cell_records.BOUNDS.fields, 'FontMono'):
                _add(record, name, asc_cell_text(cell) if name == 'Text' else cell[name])
        text = record.add('TextLines')
        for line in cell_lines(cell):
            text.add('TextLine', line)


def project_table(table, *, report=None):
    """Generate named ASC data without mutating the table or its reference graph."""
    _check(table, model.TABLE)
    output = Element('Table')
    for name, field in model.TABLE.fields.items():
        if field.getter is None and name not in ('DefFontMono', 'UnresolvedNonSignal'):
            _add(output, name, table[name])
    output.add('NonSignal', non_signal_number(table, report=report))
    output.add('Group', table['GroupId'])
    update = table.one('AutoUpdate')
    _check(update, model.UPDATE)
    for name, suffix in SETTINGS.items():
        _add(output, 'DocSettings_'+suffix, update[name])
    columns = update.one('Columns')
    _check(columns, model.COLUMNS)
    projected = output.add('DocSettings_Columns', len(columns.children()))
    titles = []
    for column in columns.children():
        _check(column, model.COLUMN)
        record = projected.add('DocSettings_Column')
        for source, destination in (('Type', 'Type'), ('TextAlign', 'Align'), ('Width', 'Width')):
            _add(record, destination, column[source])
        record.add('Name', column.get('Name', ''))
        if column.get('Title', ''):
            titles.append(column)
    rows = table.one('RowComponents')
    _check(rows, model.ROWS)
    projected = output.add('Row_Components', len(rows.children()))
    for row in rows.children():
        _check(row, model.ROW)
        record = projected.add('RowCom', len(row.children('Item')))
        for member in row.children():
            _check(member, model.MEMBER)
            record.add('pt', member['ComponentIndex'])
    _cells(table, output)
    mono = ([table] if table.get('DefFontMono', False) else [])
    mono.extend(cell for cell in table.select('Cells/Cell') if cell.get('FontMono', False))
    if titles:
        warn(report, 'table-column-title', 'asc', 'ASC omits custom documentation-column titles', titles,
             recoverability='column definitions and current cell text remain; custom regeneration titles are omitted')
    if mono:
        warn(report, 'table-font-monospace', 'asc', 'ASC omits table monospaced-font settings', mono,
             recoverability='the current font and text remain; monospaced rendering is not retained')
    return output


def project_tables(board, *, report=None):
    """Compose the current ordered table collection without copying saved keys."""
    output = Element('Tables')
    for table in collection(board, 'Tables', graphic_records.COLLECTIONS['Tables'], model.TABLE):
        output.append(project_table(table, report=report))
    return output
