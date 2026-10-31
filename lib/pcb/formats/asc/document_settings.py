"""Group ASC sheet layout and display preferences by current model ownership."""
from ...model.settings_records import LAYER_PANEL
from ...model.board_records import BOARD_FIELDS
from .values import boolean, booleans, move_fields, numeric_row, rename
from ..errors import PcbError


SHEET_FIELDS = {'PageWidth': 'SheetWidth', 'PageHeight': 'SheetHeight',
                'Left': 'LeftMargin', 'Top': 'TopMargin',
                'Right': 'RightMargin', 'Bottom': 'BottomMargin'}
DISPLAY_ALIASES = {'ContrastEdit': 'EditInactiveLayer', 'ShowFiducials': 'ShowCompFiducials'}
BOARD_ALIASES = {'RotateMarkings': 'CompRotate'}


def _discard_cached_bounds(board):
    fields = []
    for name in ('Xmin', 'Ymin', 'Xmax', 'Ymax'):
        rows = board.children(name)
        if len(rows) > 1:
            raise PcbError(f'{board.path}: ambiguous cached {name}')
        if rows:
            field = rows[0]
            if (len(field.arguments) != 1 or field.children() or
                    field.arguments[0].kind != 'number' or field.arguments[0].unit):
                raise PcbError(f'{field.path}: expected one cached coordinate')
            fields.append(field)
    for field in fields:
        field.detach()


def _consume_display_compatibility(board, settings):
    """Named PCBN markings and the root unit declaration own current choices."""
    from ....common.conversion import import_notice
    consumed = []
    for owner, names, flags in (
            (board, ('ShowText', 'TextAlign', 'ShowText2', 'TextAlign2'), False),
            (settings, ('UnitsMM', 'UnitsMIL', 'UnitsINCH', 'AssyPatMarkings'), True)):
        if owner is None:
            continue
        for name in names:
            rows = owner.children(name)
            if len(rows) > 1:
                raise PcbError(f'{owner.path}: ambiguous {name}')
            if not rows:
                continue
            field = rows[0]
            if flags:
                if len(field.arguments) != 1 or field.children():
                    raise PcbError(f'{field.path}: expected one boolean')
                boolean(field.arguments[0], field.path)
            else:
                numeric_row(field, 1, kind=name, integers=(0,))
            consumed.append(field)
    if consumed:
        import_notice('info', 'asc-display-compatibility', 'Consumed redundant ASC display fields',
            consumed, recoverability='current named markings and the root unit selection remain authoritative')
    for field in consumed:
        field.detach()


def unpack_document_settings(board):
    _discard_cached_bounds(board)
    rename(board, BOARD_ALIASES)
    booleans(board, (name for name, field in BOARD_FIELDS.items() if field.kind == 'boolean'))
    if (user_fields := board.child('Userfields_Global')) is not None:
        if user_fields.arguments:
            raise PcbError(f'{user_fields.path}: expected global user-field records')
        for row in user_fields.children():
            if row.kind not in ('Userfield', 'UserField') or row.arguments:
                raise PcbError(f'{row.path}: expected named global user-field values')
            row.kind = 'UserField'
    sheet_fields = SHEET_FIELDS
    settings = board.child('Settings')
    _consume_display_compatibility(board, settings)
    display_fields = {'DisplayTitles': 'DisplayTitles', 'DisplaySheet': 'DisplaySheet'}
    if (any(board.child(name) is not None for name in sheet_fields) or
            settings is not None and any(settings.child(name) is not None for name in display_fields)):
        sheet = board.child('SheetSettings')
        if sheet is None:
            sheet = board.add('SheetSettings')
        move_fields(board, sheet, sheet_fields)
        if settings is not None:
            move_fields(settings, sheet, display_fields)
        booleans(sheet, display_fields.values())

    panel_fields = {'LayerPanel_'+name: name for name in LAYER_PANEL.fields}
    if any(board.child(name) is not None for name in panel_fields) or board.child('LayerPanel_NonSignal') is not None:
        if settings is None:
            settings = board.add('Settings')
        panel = settings.child('LayerPanel')
        if panel is None:
            panel = settings.add('LayerPanel')
        move_fields(board, panel, panel_fields)
        booleans(panel, LAYER_PANEL.fields)
        if (choices := board.child('LayerPanel_NonSignal')) is not None:
            if choices.arguments or panel.child('NonSignals') is not None:
                raise PcbError('ambiguous non-signal display settings')
            target = panel.add('NonSignals')
            for index, row in enumerate(choices.children()):
                if row.kind != 'pt' or len(row.arguments) != 1 or row.children():
                    raise PcbError('non-signal display rows require one pt boolean')
                target.add('Item', index, boolean(row.arguments[0], row.path))
            choices.detach()

    if settings is not None:
        # These are vocabulary aliases, with the same boolean sense.
        rename(settings, DISPLAY_ALIASES)
