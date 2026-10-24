"""Footprint selection frames for detached format views.

These are compatibility selection bounds, not CAD copper or collision contours.
The public geometry stays grouped; temporary discs and vertices express the
measured selection approximation without reproducing format object structures.
"""
import math

from ...common.geometry import (polar_rotate)
from ...common.numbers import (calculation_number)
from ...common.geometry import (Bounds, circular_arc_bounds)
from ...common.model import (Value)


def _number(owner, name):
    return calculation_number(owner.one(name))


def _assign(field, value):
    # Explicit values replace the imported calculation boundary even when the
    # exact decimal happens to compare equal to its derived replacement.
    field.set_values(Value.of(value))


def _position(pad):
    return calculation_number(pad, 3), calculation_number(pad, 4)


def _set_position(pad, position):
    for index, value in zip((3, 4), position):
        pad.set_argument(index, Value.of(value))


def _surface_pad(pad):
    return pad.scalar('SurfacePad') in (True, 'Y')


def _refresh_polygon(pad):
    if pad.scalar('PadShape_New') != 3:
        return
    points = pad.select('PadPoints_New/pt')
    if not points:
        raise ValueError(f'{pad.path}: a physical polygon pad needs vertices')
    positions = [(calculation_number(point), calculation_number(point, 1)) for point in points]
    bounds = Bounds.from_points(positions)
    width, height = _number(pad, 'PadWidth_New'), _number(pad, 'PadHeight_New')
    if max(abs(bounds.left+bounds.right), abs(width-bounds.width),
           abs(bounds.top+bounds.bottom), abs(height-bounds.height)) <= .05:
        return
    if _surface_pad(pad):
        cx, cy = bounds.center
        _assign(pad.one('PadWidth_New'), bounds.width)
        _assign(pad.one('PadHeight_New'), bounds.height)
        for point, (x, y) in zip(points, positions):
            point.set_values(Value.of(x-cx), Value.of(y-cy))
        dx, dy = polar_rotate((cx, cy), _number(pad, 'PadAngle'))
        x, y = _position(pad)
        _set_position(pad, (x+dx, y+dy))
        if abs(cx) > .05 or abs(cy) > .05:
            pad.set_field('Standard', False)
    else:
        _assign(pad.one('PadWidth_New'), 2*max(abs(bounds.left), abs(bounds.right)))
        _assign(pad.one('PadHeight_New'), 2*max(abs(bounds.top), abs(bounds.bottom)))


def pad_selection_bounds(pad):
    """Read the format selection approximation, including shape-center offsets."""
    kind = pad.scalar('PadShape_New')
    width, height = (_number(pad, name) for name in ('PadWidth_New', 'PadHeight_New'))
    angle = _number(pad, 'PadAngle')
    x, y = _position(pad)
    if not _surface_pad(pad):
        dx, dy = _number(pad, 'PadShape_X'), _number(pad, 'PadShape_Y')
        if dx or dy:
            dx, dy = polar_rotate((dx, dy), angle)
            x, y = x+dx, y+dy
    a, b = width/2, height/2
    if kind == 0 and abs(width-height) < .001:
        return Bounds(x-a, y-b, x+a, y+b)
    if kind == 20:
        radius = _number(pad, 'PadHole')/2
        return Bounds(x-radius, y-radius, x+radius, y+radius)
    discs = []
    if kind == 0:
        discs = [(a*math.cos(i*(math.pi/6)), b*math.sin(i*(math.pi/6)), 0.)
                 for i in range(12)]
    elif kind == 1:
        radius = min(a, b)
        distance = abs(a-b)
        discs = ([(0., -distance, radius), (0., distance, radius)] if b > a else
                 [(-distance, 0., radius), (distance, 0., radius)])
    elif kind == 2:
        corner = min(50., max(0., _number(pad, 'PadCorner')))
        radius = min(width, height)*corner/100
        discs = [(sx*(a-radius), sy*(b-radius), radius)
                 for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    elif kind == 3:
        discs = [(calculation_number(point), calculation_number(point, 1), 0.)
                 for point in pad.select('PadPoints_New/pt')]
    elif kind == 4:
        discs = [(-a, b, 0.), (a, b, 0.), (0., -b+a if b > a else 0., min(a, b))]
    vertices = [(x, y)]  # The pad anchor participates in its selection frame.
    for dx, dy, radius in discs:
        if abs(angle) > .001:
            dx, dy = polar_rotate((dx, dy), angle)
        vertices.extend(((x+dx-radius, y+dy-radius), (x+dx+radius, y+dy+radius)))
    return Bounds.from_points(vertices)


def prepare_pattern(pattern):
    """Recompute a detached footprint frame and recenter its current geometry."""
    pads = pattern.select('Pads/Pad')[1:-1]
    shapes = pattern.select('Shapes/Shape')
    holes = pattern.select('Holes/Hole')[1:-1]
    boxes = []
    for index, pad in enumerate(pads, 1):
        if pad.scalar('Number_New') != index:
            continue  # Shared/default pad entries do not add physical bounds.
        _refresh_polygon(pad)
        if pad.scalar('PadShape_New') == 2:
            corner = _number(pad, 'PadCorner')
            if not 0 <= corner <= 50:
                _assign(pad.one('PadCorner'), min(50., max(0., corner)))
        boxes.append(pad_selection_bounds(pad))
    if shapes:
        shapes[0].set_field('Type', 0)
        shapes[-1].set_field('Type', 0)
    for shape in shapes[1:-1]:
        kind = shape.scalar('Type')
        if kind <= 0 or kind == 7:
            continue
        points = [(calculation_number(point), calculation_number(point, 1))
                  for point in shape.select('Points_New/pt')]
        box = circular_arc_bounds(*points) if kind == 6 and len(points) == 3 else Bounds.from_points(points)
        if box is not None:
            boxes.append(box)
    for hole in holes:
        if hole.values[0] not in (True, 'Y'):
            continue
        x, y, diameter = (calculation_number(hole, index) for index in (2, 3, 4))
        boxes.append(Bounds(x-diameter/2, y-diameter/2, x+diameter/2, y+diameter/2))
    bounds = None
    for box in boxes:
        bounds = box if bounds is None else bounds.union(box)
    width, height = (bounds.width, bounds.height) if bounds else (0., 0.)
    _assign(pattern.one('Width'), width if width > 0 else .0001)
    _assign(pattern.one('Height'), height if height > 0 else .0001)
    cx, cy = bounds.center if bounds else (0., 0.)
    if abs(cx) <= .00001 and abs(cy) <= .00001:
        return
    for name, offset in (('OriginX', cx), ('OriginY', cy)):
        _assign(pattern.one(name), _number(pattern, name)-offset)
    for pad in pads:
        x, y = _position(pad)
        _set_position(pad, (x-cx, y-cy))
    for shape in shapes[1:-1]:
        if shape.scalar('Type') > 0:
            for point in shape.select('Points_New/pt'):
                point.set_values(Value.of(calculation_number(point)-cx),
                                 Value.of(calculation_number(point, 1)-cy))
    for hole in holes:
        hole.set_argument(2, Value.of(calculation_number(hole, 2)-cx))
        hole.set_argument(3, Value.of(calculation_number(hole, 3)-cy))
    for dimension in pattern.select('Dimensions/Dimension'):
        for name, offset in (('X1', cx), ('Y1', cy), ('X2', cx), ('Y2', cy), ('XD', cx), ('YD', cy)):
            _assign(dimension.one(name), _number(dimension, name)-offset)
