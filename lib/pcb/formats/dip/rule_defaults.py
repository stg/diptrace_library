"""Supply current rule meaning for fields absent from earlier DIP revisions."""
from decimal import Decimal

from ....common.conversion import import_notice
from ...model.length_matching import DEFAULT_FIXED_LENGTH, DEFAULT_DELTA


def modernize_rules(decoded):
    """Resolve version-gated defaults before rule identities are bound.

    These become ordinary editable facts. No source-era copy or preferred
    historical default is retained alongside the current rules.
    """
    version, board = decoded.header.version, decoded.board
    changed = []

    def missing(record, values):
        added = False
        for name, value in values.items():
            if record.child(name) is None:
                record.add(name, value)
                added = True
        if added:
            changed.append(record)

    for net_class in board.select('NetClasses/NetClass'):
        if version < 40:
            missing(net_class, {'Phase': 6, 'Phase_ErrorLength': 15})
            for row in net_class.select('LayProperties/LayProperty'):
                missing(row, {'Neck_Width': -1, 'Neck_DifClearance': -1, 'Neck_MaxLength': 0})
        if version < 43:
            maximum = net_class.get('MaxLength', 0)
            minimum = net_class.get('MinLength', 0)
            if maximum > Decimal('.0001'):
                limits = dict(LengthDelta=abs(maximum-minimum), FixedLength=(minimum+maximum)/2)
            else:
                limits = dict(LengthDelta=DEFAULT_DELTA, FixedLength=DEFAULT_FIXED_LENGTH)
            missing(net_class, limits)

    # A missing last-used rule snapshot remains absent. A destination requiring
    # a compatibility copy can derive it from current rules during export.
    for kind in ('DRC', 'LastDRC'):
        drc = board.child(kind)
        if drc is None:
            continue
        if version < 45:
            missing(drc, {'CheckKeepouts': False, 'CheckSameNet': False, 'CheckSameComponentPads': True})
            for row in drc.select('LayClearances/LayClearance'):
                missing(row, dict.fromkeys(('SameTraceToTrace', 'SameSmdToVia', 'SameSmdToPad', 'SameSmdToSmd'), 0))
        if version < 47:
            # Earlier files have no separate silk-clearance setting. An already
            # enabled silk check inherits its existing shared clearance rules;
            # otherwise the current default is .15 mm in shared length units.
            silk = 0 if drc.scalar('CheckSilk', False) else Decimal('0.45')
            missing(drc, {'CheckCourtyard': False, 'SilkClearance': silk})

    if changed:
        import_notice('info', 'legacy-board-rules', 'Modernized earlier board rule settings.',
                      tuple(dict.fromkeys(changed)))
