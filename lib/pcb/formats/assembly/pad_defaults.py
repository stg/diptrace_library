"""Reconcile standard-pad declarations with the current footprint defaults.

A custom pad remains custom even when its values happen to match the defaults.
For a pad declared standard, import checks the geometry and applicable mask and
terminal settings before exposing that declaration in the editable model.
"""
import math

from ....common.conversion import import_notice


_DIMENSIONS = (('PadWidth_New', 'PadWidth'), ('PadHeight_New', 'PadHeight'))
_MASKS = (('DisableTopMask', 'TopMask_State'), ('DisableBottomMask', 'BotMask_State'),
          ('DisableTopPaste', 'TopPaste_State'), ('DisableBottomPaste', 'BotPaste_State'))


def _near(left, right, tolerance):
    if left is None or right is None:
        return left is right
    return abs(float(left)-float(right)) <= tolerance


def _points(owner, collection, *, mirrored=False):
    sign = -1 if mirrored else 1
    return [(sign*float(point.values[0]), float(point.values[1]))
            for point in owner.select(collection+'/pt')]


def _same_points(left, right, tolerance):
    return (len(left) == len(right) and
            all(_near(x, u, tolerance) and _near(y, v, tolerance)
                for (x, y), (u, v) in zip(left, right)))


def _same_masks(pattern, pad, mirrored):
    actual = [pad[name] for name, _ in _MASKS]
    defaults = [pattern[name] for _, name in _MASKS]
    if mirrored:
        defaults = [defaults[1], defaults[0], defaults[3], defaults[2]]
    if actual != defaults:
        return False
    relevant = []
    if any(mode < 2 for mode in actual[:2]):
        relevant.append('CustomSwell_New')
    if any(mode < 2 for mode in actual[2:]):
        relevant.append('CustomShrink_New')
    if 3 in actual[2:]:
        relevant.extend(('PadMask_Percent', 'PadMask_EdgeGap',
                         'PadMask_SegmentGap', 'PadMask_SegmentSide'))
    return all(_near(pad[name], pattern[name], .003) for name in relevant)


def _same_terminals(pattern, pad, mirrored):
    actual, defaults = pad.children('PadTerminal'), pattern.children('PadTerminal')
    if len(actual) != len(defaults):
        return False
    sign = -1 if mirrored else 1
    for terminal, default in zip(actual, defaults):
        kind = terminal['Type']
        if kind != default['Type']:
            return False
        dimensions = ('Y', 'ShapeWidth', 'ShapeHeight')
        if kind == 2:
            dimensions += ('ShapeCorner',)
        if (not _near(terminal['X'], sign*float(default['X']), .003) or
                any(not _near(terminal[name], default[name], .003) for name in dimensions)):
            return False
        angle = float(terminal['Angle']) % math.tau
        expected = (sign*float(default['Angle'])) % math.tau
        if not _near(angle, expected, math.radians(.5)):
            return False
        if kind == 3 and not _same_points(
                _points(terminal, 'ShapePoints'),
                _points(default, 'ShapePoints', mirrored=mirrored), .003):
            return False
    return True


def matches_defaults(pattern, pad, *, mirrored=False):
    """Compare the settings that determine whether a pad uses its default style.

    This comparison ignores placement, electrical identity, locking, and unused
    shape/mask options. Length tolerances are in the model's shared length unit.
    It does not change either record or promote a custom pad to standard.
    """
    kind = pad['PadShape_New']
    if kind != pattern['PadShape'] or pad['SurfacePad'] != pattern['SurfacePad']:
        return False
    if any(not _near(pad[name], pattern[default], .001) for name, default in _DIMENSIONS):
        return False
    if kind == 2 and not _near(pad['PadCorner'], pattern['PadCorner'], .001):
        return False
    if not pad['SurfacePad']:
        if (pad['PadHoleType'] != pattern['PadHoleType'] or
                not _near(pad['PadHole'], pattern['PadHole'], .001)):
            return False
        if pad['PadHoleType'] > 0 and not _near(pad['PadHoleH'], pattern['PadHoleH'], .001):
            return False
    sign = -1 if mirrored else 1
    if (not _near(pad['PadShape_X'], sign*float(pattern['PadShape_X']), .001) or
            not _near(pad['PadShape_Y'], pattern['PadShape_Y'], .001)):
        return False
    if kind == 3 and not _same_points(_points(pad, 'PadPoints_New'),
                                    _points(pattern, 'PadPoints', mirrored=mirrored), .001):
        return False
    return _same_masks(pattern, pad, mirrored) and _same_terminals(pattern, pad, mirrored)


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
