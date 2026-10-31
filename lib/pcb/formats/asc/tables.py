"""Named PCB ASC table grids and documentation settings into current records."""
from ....common.cell_records import CELL
from ....common.cell_text import unpack_asc_cell_text, modernize_cell_text
from ...model.table_records import TABLE, UPDATE
from .values import booleans, numeric_row, move_fields, rename, counted_rows
from ..errors import PcbError
from .table_settings import SETTINGS


def unpack_tables(board):
    for index, table in enumerate(board.select('Tables/Table')):
        if table.arguments:
            raise PcbError(f'{table.path}: expected named PCB table fields')
        table.set_values(index)
        booleans(table, (name for name, field in TABLE.fields.items() if field.kind == 'boolean'))
        settings = {('DocSettings_'+suffix): name for name, suffix in SETTINGS.items()}
        if any(table.child(name) is not None for name in (*settings, 'DocSettings_Columns')):
            if table.child('AutoUpdate') is not None:
                raise PcbError(f'{table.path}: duplicate table documentation settings')
            update = table.add('AutoUpdate')
            move_fields(table, update, settings)
            booleans(update, (name for name, field in UPDATE.fields.items() if field.kind == 'boolean'))
            if (columns := table.child('DocSettings_Columns')) is not None:
                columns.kind = 'Columns'
                columns.move_to(update)
                for position, column in enumerate(counted_rows(columns)):
                    if column.kind != 'DocSettings_Column' or column.arguments:
                        raise PcbError(f'{column.path}: expected named documentation column')
                    column.kind = 'Column'
                    column.set_values(position)
                    rename(column, {'Align': 'TextAlign'})
        if (rows := table.child('Row_Components')) is not None:
            rows.kind = 'RowComponents'
            for position, row in enumerate(counted_rows(rows)):
                if row.kind != 'RowCom':
                    raise PcbError(f'{row.path}: expected a table component row')
                row.kind = 'Row'
                members = counted_rows(row)
                row.set_values(position)
                for member in members:
                    member.set_values(*numeric_row(member, 1, integers=(0,)))
                    member.kind = 'Item'
        widths, heights = table.one('ColWidths'), table.one('RowHeights')
        for collection in (widths, heights):
            if collection.arguments:
                raise PcbError(f'{collection.path}: expected table sizes')
            for size in collection.children():
                size.set_values(*numeric_row(size, 1))
        columns, rows = len(widths.children()), len(heights.children())
        cells = table.one('Cells')
        if (len(cells.values) != 1 or type(cells.values[0]) is not int
                or cells.values != (columns,) or len(cells.children()) != columns*rows):
            raise PcbError(f'{cells.path}: cells do not form the declared table rectangle')
        cells.set_values()
        for position, cell in enumerate(cells.children()):
            if (cell.kind != 'Cell' or len(cell.arguments) != 7 or
                    any(value.kind != 'number' or value.unit for value in cell.arguments) or
                    any(type(value) is not int for value in cell.values[:3]) or
                    cell.values[:3] != (rows, position//rows, position % rows)):
                raise PcbError(f'{cell.path}: invalid ASC cell position')
            cell.set_values(*cell.arguments[3:])
            booleans(cell, (name for name, field in CELL.fields.items() if field.kind == 'boolean'))
            if (lines := cell.child('TextLines')) is not None:
                if lines.arguments:
                    raise PcbError(f'{lines.path}: expected cell text lines')
                lines.kind = 'TextLine'
                for line in lines.children():
                    if line.kind != 'TextLine':
                        raise PcbError(f'{line.path}: expected one cell text line')
                    line.kind = 'pt'
            unpack_asc_cell_text(cell)
    modernize_cell_text(board, paths=('Tables/Table/Cells/Cell',))
