"""Named PCB ASC design-check result flags."""
from .values import booleans, boolean, rename, counted_rows
from ..errors import PcbError


def unpack_results(board):
    for error in board.select('DesignErrors/DesignError'):
        rename(error, {'RuleLayer': 'RuleLay', 'Layers': 'Lays'})
        booleans(error, ('Enabled',))
        mask = error.child('Lays')
        if mask is not None:
            for row in counted_rows(mask):
                if row.kind != 'pt' or row.children() or len(row.arguments) != 1:
                    raise PcbError(f'{row.path}: expected one layer flag')
                row.set_values(boolean(row.arguments[0], row.path))
                row.kind = 'Item'
