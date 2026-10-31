"""Independent coordinate queries for established dimension anchor domains.

These calculations do not move annotation geometry or refresh an entire board.
An unavailable calculation returns None; unresolved identities remain errors.
"""
from ...common.geometry import transform_point
from .dimensions import LOCAL_ROLES, BOARD_ROLES, BOARD_VERTEX_TYPES
from .relationships import linked


def _point(node):
    try:
        return node['X'], node['Y']
    except KeyError:
        return None


def _points(shape):
    collection = shape.child('Points_New')
    if collection is None:
        collection = shape.child('Points')
    return collection.children('pt') if collection is not None else ()


def _shape_anchor(shape, number, *, board):
    rows = _points(shape)
    kind = shape['Type']
    point_types = BOARD_VERTEX_TYPES if board else (1, 6, 8, 9)
    if kind in point_types:
        return _point(rows[number]) if 0 <= number < len(rows) else None
    if kind in ((2, 3) if board else (2, 4)) and len(rows) >= 2 and 0 <= number < 4:
        ax, ay = _point(rows[0])
        bx, by = _point(rows[1])
        return ((ax, ay), (bx, by), (ax, by), (bx, ay))[number]
    if kind in ((4, 5) if board else (3, 5)) and len(rows) >= 2 and 0 <= number < 5:
        ax, ay = _point(rows[0])
        bx, by = _point(rows[1])
        cx, cy = (ax+bx)/2, (ay+by)/2
        left, right, top, bottom = min(ax, bx), max(ax, bx), min(ay, by), max(ay, by)
        return ((left, cy), (right, cy), (cx, top), (cx, bottom), (cx, cy))[number]
    return None


def _component(pattern):
    parent = pattern.parent
    return parent if parent is not None and parent.kind == 'Component' else None


def _to_board(component, point):
    return transform_point(point, origin=(component['X'], component['Y']), angle=component['Angle'])


def attachment_position(dimension, end):
    """Return a supported endpoint anchor in its document's coordinate frame.

    Cached/local dimension results use their footprint frame. Board dimension
    results use board coordinates. Free endpoints retain their authored X/Y.
    Radius geometry, terminal anchors, pad-edge grids, text/picture bounds and
    panel bounds still require their own mappings.
    This query does not change stored coordinates or decide import/export policy.
    """
    if type(end) is not int or end not in (1, 2):
        raise ValueError('dimension endpoint must be 1 or 2')
    document = dimension._owner()
    if (dimension.kind != 'Dimension' or document is None or document.representation != 'pcb'
            or dimension.parent is None):
        raise TypeError('attachment_position requires an attached PCB dimension')
    side = str(end)
    if dimension.get('Type', 0) == 3:
        return None
    mode = dimension['Connected'+side]
    if mode < 0:
        try:
            return dimension['X'+side], dimension['Y'+side]
        except KeyError:
            return None
    board = dimension.parent.parent.kind == 'Board'
    target = linked(dimension, (BOARD_ROLES if board else LOCAL_ROLES)[end-1])
    if target is None:
        return None
    anchor = dimension['Point'+side]
    if board and mode in (3, 4, 6):
        return _point(target)
    if board and mode == 5:
        return _point(target) if target.kind == 'pt' else _shape_anchor(target, anchor, board=True)
    if board and mode == 7:
        pattern = target.one('Pattern')
        return _to_board(target, (pattern['OriginX'], pattern['OriginY']))

    if mode == 0:
        if target.kind == 'pt':
            pad = target.parent.parent
            point = _point(target)
            if point is None:
                return None
            point = transform_point(point, origin=(pad['X'], pad['Y']), angle=pad['PadAngle'])
        elif anchor == 0:
            pad, point = target, _point(target)
        else:
            return None
        component = _component(pad.parent.parent)
    elif mode == 1:
        shape = target.parent.parent if target.kind == 'pt' else target
        point = _point(target) if target.kind == 'pt' else _shape_anchor(shape, anchor, board=False)
        component = _component(shape.parent.parent)
    elif mode == 2 and anchor == 0:
        point = _point(target)
        component = _component(target.parent.parent)
    else:
        return None
    return _to_board(component, point) if point is not None and board and component is not None else point
