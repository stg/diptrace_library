"""Modernize symbol drawings without coupling them to a document format."""
import math

from .geometry import ellipse_points, unequal_extents


def expand_legacy_drawing(shape, *, orientation=0):
    """Replace corner-based text/ellipse geometry with current drawing points.

    The caller chooses the version gate and supplies the old quarter-turn
    orientation. Points are already in physical units; no footprint scaling
    applies to symbol geometry.
    """
    geometry = shape.child('Points')
    if geometry is None or shape.child('Points_New') is not None:
        raise ValueError(f'{shape.path}: expected one legacy point collection')
    geometry.kind = 'Points_New'
    kind = shape.scalar('Type')
    points = geometry.children('pt')
    if kind == 10 and len(points) > 1:
        first, last = points[0].arguments, points[1].arguments
        anchors = {1: (first[0], last[1]), 2: last, 3: (last[0], first[1])}
        points[0].set_values(*anchors.get(orientation, first))
        for point in points[1:]:
            point.detach()
    elif kind in (6, 7) and len(points) >= 2:
        first, last = (point.values for point in points[:2])
        if unequal_extents(first, last, tolerance='.3'):
            for point in points:
                point.detach()
            for point in ellipse_points(first, last, segments=30, closed=kind == 6):
                geometry.add('pt', *point)
            shape.set_field('Type', 8 if kind == 6 else 9)
    for name, value in (('TextAngle', orientation*math.pi/2), ('TextHorz', -1),
                        ('TextVert', -1), ('TextAlign', -1), ('LineSpacing', 1.2)):
        shape.add(name, value).annotations['derived_from'] = 'legacy drawing settings'
