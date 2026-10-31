"""Read ASC panel settings without recalculating panel tabs or board geometry."""
from ...model.board_records import PANEL
from .values import booleans, move_fields, numeric_row
from ..errors import PcbError


GAPS = ('LeftGap', 'RightGap', 'TopGap', 'BottomGap')
PANEL_FIELDS = {'Panelize_'+name: name for name in PANEL.fields
                if name not in ('PanelizeSingle', *GAPS)}
PANEL_FIELDS.update(Panelize_Single='PanelizeSingle', Panelize_HorzTabX='HorzTabsX',
                    Panelize_VertTabY='VertTabsY')


def unpack_panel(board):
    fields = PANEL_FIELDS
    if not any(board.child(name) is not None for name in fields):
        return
    panel = board.child('Panel')
    if panel is None:
        panel = board.add('Panel')
    move_fields(board, panel, fields)
    booleans(panel, (name for name, field in PANEL.fields.items() if field.kind == 'boolean'))
    for name in ('HorzTabsX', 'VertTabsY'):
        positions = panel.child(name)
        if positions is None:
            continue
        if positions.values:
            raise PcbError(f'{positions.path}: expected tab positions')
        for row in positions.children():
            row.set_values(*numeric_row(row, 1))
            row.kind = 'Item'
