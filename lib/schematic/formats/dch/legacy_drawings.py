"""Convert old normalized footprint drawings into editable physical geometry.

The adapter owns only version-specific choices. Scaling and ellipse sampling use
ordinary geometry operations; no format scratch records or allocator are used.
"""
import math

from ...model.traversal import (footprints, symbols)
from ....common.geometry import (ellipse_points)
from .data import (stored_data)


def expand_symbol_drawings(version, schematic):
    """Give old symbol and schematic drawings their editable modern geometry."""
    if version >= 40:
        return
    owners = list(symbols(schematic)) + [schematic]
    for owner in owners:
        shapes = owner.child('Shapes')
        for shape in shapes.children('Shape') if shapes else ():
            expand_symbol_drawing(shape)
            if owner.parent is not None and owner.parent.kind == 'Components' and shape.scalar('MarkingGenerated'):
                clear_legacy_marking(shape)


def clear_legacy_marking(shape):
    """The old placed marking is regenerated later, from current label data."""
    for name, value in (('Enabled', False), ('Type', 0)):
        shape.set_field(name, value)
    for point in tuple(shape.child('Points_New').children('pt')):
        point.detach()
    lines = shape.child('TextLine')
    if lines is not None:
        for line in tuple(lines.children()):
            line.detach()
    shape.set_field('MarkingGenerated', False)


def expand_symbol_drawing(shape):
    """Upgrade geometry without reproducing the format drawing record."""
    geometry = shape.child('Points')
    if geometry is None or shape.child('Points_New') is not None:
        raise ValueError(f'{shape.path}: expected one legacy point collection')
    geometry.kind = 'Points_New'
    stored = shape.child('StoredData')
    orientation = shape.scalar('Orientation', stored.scalar('Orientation', 0) if stored is not None else 0)
    kind = shape.scalar('Type')
    points = geometry.children('pt')
    if kind == 10 and len(points) > 1:
        first, last = points[0].arguments, points[1].arguments
        anchors = {1: (first[0], last[1]), 2: last, 3: (last[0], first[1])}
        points[0].set_values(*anchors.get(orientation, first))
        for point in points[1:]:
            point.detach()
    elif kind in (6, 7) and len(points) >= 2:
        first, last = (tuple(map(float, point.values)) for point in points[:2])
        width, height = abs(last[0]-first[0]), abs(last[1]-first[1])
        if abs(width-height) > .3:
            for point in points:
                point.detach()
            for point in ellipse_points(first, last, segments=30, closed=kind == 6):
                geometry.add('pt', *point)
            shape.set_field('Type', 8 if kind == 6 else 9)
    for name, value in (('TextAngle', orientation*math.pi/2), ('TextHorz', -1),
                        ('TextVert', -1), ('TextAlign', -1), ('LineSpacing', 1.2)):
        shape.add(name, value).annotations['derived_from'] = 'legacy drawing settings'


def expand_pattern_drawings(version, schematic):
    if version >= 40:
        return
    for pattern in footprints(schematic):
        scale = float(pattern.scalar('Width')), float(pattern.scalar('Height'))
        shapes = pattern.child('Shapes').children('Shape')
        for index, shape in enumerate(shapes):
            if (pattern.parent.kind == 'Part' and shape.scalar('Type') < 0
                    and index not in (0, len(shapes)-1)):
                shape.annotations['asc_omit'] = 'disabled interior footprint drawing'
            expand_drawing(shape, scale)


def expand_drawing(shape, scale):
    """Upgrade one drawing using the original footprint's coordinate scale."""
    kind = shape.scalar('Type')
    stored = stored_data(shape)
    raw = tuple(map(float, stored.child('CompatibilityGeometry').values))
    corners = tuple(zip(raw[::2], raw[1::2]))
    geometry = shape.child('Points_New')
    if kind == 0:
        points = ()
    elif kind == 7:
        orientation = stored.scalar('TextOrientation')
        x, y = corners[0]
        right, bottom = corners[1]
        anchors = ((x, y), (x, bottom), (right, bottom), (right, y))
        points = (anchors[orientation],) if 0 <= orientation < 4 else ()
    elif kind < 8:
        points = corners[:3 if kind == 6 else 2]
    else:
        points = [tuple(map(float, p.values)) for p in geometry.children('pt')]
    physical = [(float(x)*scale[0], float(y)*scale[1]) for x, y in points]
    if kind in (3, 5) and len(physical) == 2:
        a, b = physical
        if abs(abs(b[0]-a[0])-abs(b[1]-a[1])) > .3:
            physical = ellipse_points(a, b, segments=30, closed=kind == 3)
            shape.set_field('Type', 8 if kind == 3 else 9)
    for point in tuple(geometry.children()):
        point.detach()
    for x, y in physical:
        geometry.add('pt', x, y)
    orientation = stored.scalar('TextOrientation') if kind == 7 else 0
    for name, value in (('TextAngle', orientation*math.pi/2),
                        ('TextHorz', -1 if kind == 7 else 0),
                        ('TextVert', -1 if kind == 7 else 0), ('TextAlign', -1),
                        ('LineSpacing', 1.2), ('AllLayers', False), ('Group', -1)):
        shape.add(name, value).annotations['derived_from'] = 'legacy drawing settings'
    for name in ('CompatibilityGeometry', 'CompatibilityPoints', 'TextOrientation', 'Type'):
        for field in stored.children(name):
            field.detach()
    if not stored.children() and not stored.arguments:
        stored.detach()
