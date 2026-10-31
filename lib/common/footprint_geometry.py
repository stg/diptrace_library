"""Physical geometry from the older normalized footprint drawing vocabulary."""
import math
from .geometry import ellipse_points, unequal_extents


def expand_normalized_drawing(kind, controls, outline, size, *, text_orientation=0,
                              text_mirrored=False):
    """Return the current type and physical points for one footprint drawing.

    Primitive controls and polygon outlines are normalized to the footprint's
    width and height. Text uses the corner selected by its quarter-turn value;
    a mirrored text box selects the opposite horizontal corner.
    Noncircular ellipses become polygonal outlines in the current representation.
    Version policy and text style defaults belong to the document adapters.
    """
    if kind == 0:
        points = ()
    elif kind == 7:
        (left, top), (right, bottom) = controls[:2]
        if text_mirrored:
            left, right = right, left
        corners = ((left, top), (left, bottom), (right, bottom), (right, top))
        points = (corners[text_orientation],) if 0 <= text_orientation < 4 else ()
    elif kind < 8:
        points = controls[:3 if kind == 6 else 2]
    else:
        points = outline
    size = tuple(size)
    width, height = map(float, size)
    physical = tuple((float(x)*width, float(y)*height) for x, y in points)
    if kind in (3, 5) and len(physical) == 2:
        first, opposite = physical
        if unequal_extents(points[0], points[1], scale=size, tolerance='.3'):
            physical = ellipse_points(first, opposite, segments=30, closed=kind == 3)
            kind = 8 if kind == 3 else 9
    return kind, physical


def legacy_pad_outline(kind, width, height):
    """Sample an older basic pad in its own local axes, without rotation.

    Curved pad contours and footprint drawing contours have different sampling
    rules. These points describe the old pad's explicit polygon representation;
    they are not an application font/shape table. Closure is implicit.
    """
    width, height = float(width), float(height)
    rx, ry = width/2, height/2
    if kind == 0:
        return ellipse_points((-rx, -ry), (rx, ry), segments=20)
    if kind == 1:
        radius = min(rx, ry)
        horizontal = width > height
        offset = abs(rx-ry)
        points = []
        for side in (1, -1):
            for step in range(8):
                angle = math.pi/2-step*math.pi/7 if side == 1 else -math.pi/2-step*math.pi/7
                x, y = side*offset+radius*math.cos(angle), radius*math.sin(angle)
                points.append((x, y) if horizontal else (y, x))
        return tuple(points)
    if kind == 2:
        return ((-rx, -ry), (rx, -ry), (rx, ry), (-rx, ry))
    if kind == 4:
        center_y = -ry+rx
        cap = tuple((rx*math.cos(math.pi+step*math.pi/12),
                     center_y+rx*math.sin(math.pi+step*math.pi/12)) for step in range(1, 13))
        return ((rx, ry), (-rx, ry), (-rx, center_y), *cap)
    raise NotImplementedError(f'old pad contour for shape {kind} is not defined')
