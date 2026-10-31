"""Named ASC connection columns into shared ratline import fields."""
from .values import numeric_row
from ..errors import PcbError


def unpack_ratlines(board):
    source = board.child('Connections')
    if source is None:
        return
    if source.arguments:
        raise PcbError(f'{source.path}: expected connection records')
    fields = ('Enabled', 'X1', 'Y1', 'X2', 'Y2', 'Comp1', 'Comp2', 'Pad1', 'Pad2', 'Hidden')
    for index, row in enumerate(source.children()):
        values = numeric_row(row, 10, kind='Connection', flags=(0, 9), integers=(5, 6, 7, 8))
        row.set_values(index)
        for name, value in zip(fields, values):
            row.add(name, value)
