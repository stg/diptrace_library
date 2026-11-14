"""Local dimension selectors shared by footprint-bearing document families."""
from .references import Guard, Index


def matches_local_attachment(pattern, mode, anchor, target):
    """Check an attachment's physical domain in a single footprint frame."""
    parent = target.parent
    if parent is None:
        return False
    if mode == 0:
        return target.kind == 'Pad' and parent is pattern.child('Pads')
    if mode == 2:
        return target.kind == 'Hole' and parent is pattern.child('Holes') and target['Enabled']
    if mode == 1:
        shape = target if target.kind == 'Shape' else parent.parent if parent.kind == 'Points_New' else None
        if shape is None or shape.parent is not pattern.child('Shapes'):
            return False
        return (target.kind == 'pt' if shape['Type'] in (8, 9)
                else target is shape and shape['Type'] > 0)
    if mode == 3:
        terminal = (target if target.kind == 'PadTerminal'
                    else parent.parent if parent.kind == 'ShapePoints' else None)
        pad = terminal.parent if terminal is not None else None
        if pad is None or pad.kind != 'Pad' or pad.parent is not pattern.child('Pads'):
            return False
        polygon_vertex = terminal['Type'] == 3 and anchor > 0
        return target.kind == 'pt' if polygon_vertex else target is terminal
    return False


def local_scopes(pattern, dimension, side, objects):
    """Collections that constrain an available or unresolved local selector."""
    mode = dimension['Connected'+side]
    collection = pattern.child({0: 'Pads', 1: 'Shapes', 2: 'Holes', 3: 'Pads'}.get(mode, ''))
    scopes = [collection] if collection is not None else []
    if mode == 1:
        shape = objects[1].get(dimension['SubObject'+side])
        if shape is not None and (points := shape.child('Points_New')) is not None:
            scopes.append(points)
    elif mode == 3:
        pad = objects[0].get(dimension['Object'+side])
        if pad is not None:
            scopes.append(pad)
            scopes.extend(points for terminal in pad.children('PadTerminal')
                          if (points := terminal.child('ShapePoints')) is not None)
    return tuple(scopes)


def _integer(value):
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if number == value else None


def _at(records, position):
    position = _integer(position)
    return records[position] if position is not None and 0 <= position < len(records) else None


def local_attachment(dimension, side, objects, *, offset=0):
    """Resolve one endpoint using import-position maps, then project current order.

    ``objects`` maps pad/shape/hole mode numbers to position-keyed records.
    Families choose their own current object-number offset. Polyline vertices
    and terminals are zero based; a polygon-terminal vertex is one based, with
    zero reserved for the terminal itself.
    """
    mode = dimension.child('Connected'+side)
    owner = dimension.child('Object'+side)
    member = dimension.child('SubObject'+side)
    point = dimension.child('Point'+side)
    if mode is None or member is None:
        return
    selected, number = _integer(mode.values[0]), _integer(member.values[0])
    if selected is None or selected < 0:
        return
    guards = (Guard(mode, mode.values),)
    if selected in (0, 1, 2):
        target = objects[selected].get(number)
        if selected == 1 and target is not None:
            kind = _integer(target.get('Type', 1))
            if kind is not None and kind < 1:
                target = None
            elif kind in (8, 9):
                if point is not None:
                    target = _at(target.select('Points_New/pt'), point.values[0])
                    return target, (Index(member, ancestor=2, offset=offset), Index(point)), guards
                target = None
        if selected == 2 and target is not None and target.values and target.values[0] in (False, 'N'):
            target = None
        return target, (Index(member, offset=offset),), guards
    if selected == 3 and owner is not None:
        pad = objects[0].get(_integer(owner.values[0]))
        terminal = _at(pad.children('PadTerminal'), number) if pad is not None else None
        anchor = _integer(point.values[0]) if point is not None else None
        if terminal is not None and terminal.get('Type') == 3 and anchor is not None and anchor > 0:
            target = _at(terminal.select('ShapePoints/pt'), anchor-1)
            return target, (Index(owner, ancestor=3, offset=offset),
                            Index(member, ancestor=2), Index(point, offset=1)), guards
        return terminal, (Index(owner, ancestor=1, offset=offset), Index(member)), guards
    return None, (Index(member),), guards
