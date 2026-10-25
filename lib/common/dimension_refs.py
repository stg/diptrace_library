"""Local dimension selectors shared by footprint-bearing document families."""
from .references import Guard, Index


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
