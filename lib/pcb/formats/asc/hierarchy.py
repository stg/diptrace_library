"""Prepare named schematic hierarchy metadata from PCB ASC declarations."""
from .values import rename
from ..errors import PcbError


def unpack_hierarchy(board):
    rename(board, {'Hierarchy_Sheets': 'HierarchySheets'})
    sheets = board.child('HierarchySheets')
    if sheets is None:
        return
    if sheets.values:
        raise PcbError(f'{sheets.path}: expected hierarchy sheet records')
    for sheet in sheets.children():
        if (sheet.kind != 'HSheet' or len(sheet.values) != 2 or
                not isinstance(sheet.values[0], str) or type(sheet.values[1]) is not int):
            raise PcbError(f'{sheet.path}: expected hierarchy sheet name and identifier')
        rows = sheet.children()
        for row in rows:
            if (row.kind != 'pt' or len(row.values) != 2 or row.children() or
                    type(row.values[0]) is not int or not isinstance(row.values[1], str)):
                raise PcbError(f'{row.path}: expected hierarchy block identifier and name')
        blocks = sheet.add('UpdateIds')
        for row in rows:
            row.kind = 'UId'
            row.move_to(blocks)
