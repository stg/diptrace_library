"""Modernize older DIP properties that have defined current values."""
from decimal import Decimal

from ....common.conversion import import_notice


def modernize_properties(decoded):
    """Supply omitted earlier settings, independently of destination formats.

    These are loader defaults with separate introduction gates. Optional paths
    and unavailable calculated data are not inferred by this pass.
    """
    version, board = decoded.header.version, decoded.board
    changed = []

    def missing(owner, values):
        added = False
        for name, value in values.items():
            if owner.child(name) is None:
                owner.add(name, value)
                added = True
        if added:
            changed.append(owner)

    patterns = board.select('Components/Component/Pattern')
    patterns += board.select('CacheLib/Slots/Slot/Definition/Pattern')
    for pattern in patterns:
        model = pattern.child('Model3D')
        if model is None:
            continue
        if version < 47:
            missing(model, dict(IPC_XOff=0, IPC_YOff=0, AutoHeight=0,
                                AutoColor=0x4B4B4B, Type=0))
        if version < 50:
            missing(model, {'KeepPins': False})
    if version < 48:
        for pin in board.select('CacheLib/Slots/Slot/Definition/Part/Pins/Pin'):
            missing(pin, dict(PinNameRotate=0, PinNumRotate=0))

    if version < 47:
        for field in board.select('SheetSettings/TitleBlocks/TitleBlock/Contents/Content'):
            missing(field, {'LineSpacing': Decimal('1.2')})

    if version < 50:
        # Earlier files omit the entire tab-routing configuration. These become
        # ordinary editable settings on import, in the model's shared lengths.
        panel = board.child('Panel')
        if panel is None:
            panel = board.add('Panel')
        missing(panel, dict(Type=0, BorderTabs=0, TabsDone=False, KeepMaterial=False,
            TabStep=225, TabWidth=Decimal('13.5'), TabRadius=Decimal('3.6'),
            CombinedRadius=Decimal('3.6'), HoleDiam=Decimal('2.4'),
            HoleStep=Decimal('3.6'), HoleInset=0, HoleKeepout=3))
        for name in ('HorzTabsX', 'VertTabsY'):
            if panel.child(name) is None:
                panel.add(name)

    if version < 55 and (panel := board.child('Panel')) is not None:
        missing(panel, {name: board[source] for name, source in
            (('LeftGap', 'PanelDX'), ('RightGap', 'PanelDX'),
             ('TopGap', 'PanelDY'), ('BottomGap', 'PanelDY'))})

    if changed:
        import_notice('info', 'legacy-board-properties',
                      'Modernized earlier PCB property representations.',
                      tuple(dict.fromkeys(changed)))
