"""PCB import policy for pads declared to use their footprint defaults."""
from ....common.conversion import import_notice
from ....common.pad_defaults import matches_defaults


def normalize_standard_pads(board):
    """Validate physical pad declarations before import removes boundary slots.

    Only an interior pad whose saved geometry marker equals its array position
    participates. Electrical keys, deleted entries and fiducial shapes do not
    establish eligibility for this load-time normalization.
    """
    changed = []
    for component in board.select('Components/Component'):
        if not component.get('Enabled', True):
            continue
        pattern = component.one('Pattern')
        for position, pad in enumerate(pattern.select('Pads/Pad')[1:-1], 1):
            if (pad['Number_New'] != position or not pad.get('Standard', False) or
                    pad['PadShape_New'] == 20):
                continue
            mirrored = component.get('BottomSide', False) != pad['Sided']
            if not matches_defaults(pattern, pad, mirrored=mirrored):
                pad.set_field('Standard', False)
                changed.append(pad)
    if changed:
        import_notice('info', 'pad-default-status',
                      'Marked pads with individual geometry or mask settings as custom.', changed)
