"""Stable binary coordinate frames derived from current footprint anchors."""
from ....common.binary import quantized_number
from ....common.conversion import info
from ..placement_frames import project_frame


def _exact_geometry(component):
    """Keep a centered, already representable frame without re-encoding it."""
    pattern = component.one('Pattern')
    values = [component.get(name, 0) for name in ('X', 'Y')]
    for pad in pattern.select('Pads/Pad'):
        values.extend(pad.get(name, 0) for name in ('X', 'Y', 'PadAngle', 'PadWidth_New',
            'PadHeight_New', 'PadShape_X', 'PadShape_Y', 'PadCorner'))
        values.extend(value for point in pad.select('PadPoints_New/pt') for value in point.values)
    for shape in pattern.select('Shapes/Shape'):
        if shape.get('Type', 0) > 0 and shape['Type'] != 7:
            values.extend(value for point in shape.select('Points_New/pt') for value in point.values)
    for hole in pattern.select('Holes/Hole'):
        if hole['Enabled']:
            values.extend(hole[name] for name in ('X', 'Y', 'Diam'))
    try:
        return all(value is None or quantized_number(value, format_name='DIP') == value for value in values)
    except (ValueError, TypeError):
        # A change of frame may make local coordinates representable. The
        # actual writer still validates every projected scalar and its range.
        return False


def _anchors(pattern):
    """Prefer the authored origin, then physical points in semantic order.

    A distant origin can exceed the binary range after placement compensation.
    Each alternative is also a current point that follows frame translations;
    no serialized-frame history is needed to recover it after loading.
    """
    yield pattern.get('OriginX', 0), pattern.get('OriginY', 0)
    for pad in pattern.select('Pads/Pad'):
        yield pad['X'], pad['Y']
    for shape in pattern.select('Shapes/Shape'):
        if shape.get('Type', 0) > 0 and shape['Type'] != 7:
            yield from (point.values for point in shape.select('Points_New/pt'))
    for hole in pattern.select('Holes/Hole'):
        if hole['Enabled']:
            yield hole['X'], hole['Y']


def project_frames(board, *, report=None):
    """Adapt a detached view, without retaining a previous serialized frame.

    After loading, origin and geometry have received the same local translation.
    Writing relative to that origin recovers the same rounded values next time.
    Placement uses the angle actually written, so its compensation cancels too.
    """
    common_fiducials = board.one('Settings').get('ShowCompFiducials', True)
    changed = []
    for component in board.select('Components/Component'):
        if not component.get('Enabled', True):
            continue
        pattern = component.one('Pattern')
        # These standalone objects have no independently translated origin.
        # Their existing initialization/frame rules remain authoritative.
        if pattern['Type'] in (15, 16):
            continue
        if _exact_geometry(component):
            continue
        angle = quantized_number(component.get('Angle', 0), format_name='DIP')
        for origin in _anchors(pattern):
            try:
                projected = project_frame(component, origin, angle=angle,
                    common_fiducials=common_fiducials,
                    check_number=lambda value: quantized_number(value, format_name='DIP'))
            except ValueError:
                continue
            if projected:
                changed.append(component)
            break
    if changed:
        info(report, 'binary-footprint-frame', 'dip',
             'Binary output uses a footprint reference point to stabilize its coordinate frame.', changed,
             recoverability='loading reconstructs the centered frame; source data and world geometry remain')
