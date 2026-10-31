"""Read-only compatibility views of the current PCB routing relationships."""
import math

from ..model.pair_routing import SEGMENT_TRACES
from ..model.pair_membership import CONNECTION, member_center


def via_geometry(style):
    """Generate compatibility geometry from a current selected style identity."""
    if style is None:
        return dict(ViaSize=0, ViaRing=0, ThroughVia=False, ViaHole=0, ViaFrom=-1, ViaTo=-1)
    size, hole = style['Size'], style['HoleSize']
    return dict(ViaSize=size, ViaRing=(size-hole)/2, ThroughVia=style['Through'],
                ViaHole=hole, ViaFrom=style['Lay1'], ViaTo=style['Lay2'])


def peer_backlink(trace):
    """Format cache index; segment geometry suppresses this redundant backlink.

    The model's SeparateTrace identity and its index view remain available.
    Projection does not disconnect that relationship or alter either trace.
    """
    document = trace._owner()
    if document and any(document.references.incoming(trace, role=role) for role in SEGMENT_TRACES):
        return -1
    return trace['PairSeparateTrace']


def point_memberships(trace):
    """Yield current center/subpoint indices, including generated connection runs.

    Runs follow trace order and reset at any point outside a connection center.
    Project in one pass; do not retain sequence counters in the editable model.
    """
    run = 0
    for point in trace.one('Points')._child_sequence('Point'):
        center = member_center(point['PairTarget'])
        if center is not None and center.get('Type', 0) == CONNECTION:
            run += 1
            yield center._ordinal(), run
        else:
            run = 0
            yield point['PairPoint'], point['PairSubPoint']


def _direction(dx, dy, tolerance):
    candidates = ((abs(dx), 2), (abs(dy), 1), (abs(dx-dy), 3), (abs(dx+dy), 4))
    return next((code for residual, code in candidates if residual < tolerance), 0)


def _value(point, name):
    return point.get(name, point.schema.fields[name].default)


def center_directions(points):
    """Derived incoming directions for a differential segment's center line."""
    for index, point in enumerate(points):
        if index == 0:
            yield 0
            continue
        dx = float(_value(point, 'X'))-float(_value(points[index-1], 'X'))
        dy = float(_value(point, 'Y'))-float(_value(points[index-1], 'Y'))
        yield _direction(dx, dy, min(math.hypot(dx, dy)/30, .5))


def point_directions(points):
    """Incoming-segment compatibility codes, generated from current geometry.

    Codes distinguish horizontal, vertical and the two diagonal families. Arc
    control points and arbitrary segments use zero. This is a classification;
    it never snaps coordinates or changes the actual route.
    """
    arcs = tuple(_value(point, 'Arc') for point in points)
    fixed_tolerance = any(arcs[1:-1])
    for index, point in enumerate(points):
        if index == 0 or arcs[index] or arcs[index-1]:
            yield 0
            continue
        dx = float(_value(point, 'X'))-float(_value(points[index-1], 'X'))
        dy = float(_value(point, 'Y'))-float(_value(points[index-1], 'Y'))
        tolerance = .05 if fixed_tolerance else min(math.hypot(dx, dy)/30, .5)
        yield _direction(dx, dy, tolerance)
