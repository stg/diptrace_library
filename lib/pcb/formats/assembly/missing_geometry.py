"""Unavailable placed copper dimensions use absence in the editable model."""
from ....common.conversion import import_notice, info


DIMENSIONS = ('PadWidth_New', 'PadHeight_New')


def unavailable_size(value):
    """Recognize the format's sentinel at its binary64 scalar boundary."""
    return value is not None and float(value) == -1


def normalize_sizes(board):
    """Consume the negative-one scalar marker after selected styles resolve.

    XML unit conversion may retain more decimal precision than the receiving
    binary64 length. Marker recognition uses that scalar boundary, without an
    arbitrary numerical tolerance or a second availability flag.
    """
    changed = []
    for component in board.select('Components/Component'):
        if not component.get('Enabled', True):
            continue
        for pad in component.select('Pattern/Pads/Pad')[1:-1]:
            if pad.get('Number_New', -1) < 0:
                continue
            for name in DIMENSIONS:
                value = pad.get(name)
                if unavailable_size(value):
                    pad.set_field(name, None)
                    changed.append(pad)
    if changed:
        import_notice('info', 'unavailable-pad-geometry',
                      'Represented unavailable copper dimensions as None.', tuple(dict.fromkeys(changed)),
                      recoverability='pad position and connections remain; a selected style or explicit dimensions supply geometry')


def materialize_sizes(board, *, destination, report=None):
    """Generate required scalar markers only on the detached export view."""
    changed = []
    for pad in board.select('Components/Component/Pattern/Pads/Pad'):
        for name in DIMENSIONS:
            if pad.get(name) is None:
                pad[name] = -1
                changed.append(pad)
    if changed:
        info(report, 'unavailable-pad-geometry', destination,
             'Encoded unavailable copper dimensions with the destination scalar marker.',
             tuple(dict.fromkeys(changed)),
             recoverability='unavailable geometry remains unavailable; the authoring model is unchanged')
