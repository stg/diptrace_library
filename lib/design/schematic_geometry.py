"""Geometry views over public schematic elements, usable after either import."""
import math

from .geometry import Bounds, circular_arc_bounds


def _enabled(node, field):
    return node.scalar(field) in (True, 'Y')


def symbol_bounds(part):
    """Local symbol bounds from enabled pins and ordinary non-text drawings.

    This is the authoring geometry. Generated markings and text need a font
    layout service and do not determine this box. The placed position, rotation
    and pen width are deliberately outside this local coordinate calculation.
    """
    boxes = []
    pins = part.child('Pins')
    if pins:
        box = Bounds.from_points(pin.values[1:3] for pin in pins.children('Pin')
                                 if _enabled(pin, 'Enabled'))
        if box:
            boxes.append(box)
    shapes = part.child('Shapes')
    for shape in shapes.children('Shape') if shapes else ():
        if not _enabled(shape, 'Enabled') or _enabled(shape, 'MarkingGenerated') or shape.scalar('Type') == 10:
            continue
        geometry = shape.child('Points_New') or shape.child('Points')
        points = [point.values[:2] for point in geometry.children('pt')] if geometry else []
        if shape.scalar('Type') == 2:
            if len(points) != 3:
                raise ValueError(f'{shape.path}: an arc requires three defining points')
            box = circular_arc_bounds(*points)
        else:
            box = Bounds.from_points(points)
        if box:
            boxes.append(box)
    if not boxes:
        return None
    result = boxes[0]
    for box in boxes[1:]:
        result = result.union(box)
    return result


def pattern_bounds(pattern):
    """Local footprint bounds, including pads, holes and non-text drawings.

    Pad bounds currently support orthogonal rotations. General pad contours and
    arbitrary rotations need their own contour view rather than a rectangle
    approximation. Unsupported rotations are explicit errors.
    """
    boxes = []
    pads = pattern.child('Pads')
    for pad in pads.children('Pad') if pads else ():
        if pad.annotations.get('reserved'):
            continue
        width, height = float(pad.scalar('PadWidth_New')), float(pad.scalar('PadHeight_New'))
        if not width and not height:
            continue  # Reserved array records have no physical geometry.
        angle = float(pad.scalar('PadAngle', 0))
        quarter = round(angle/(math.pi/2))
        if abs(angle-quarter*math.pi/2) > 1e-9:
            raise NotImplementedError(f'{pad.path}: bounds for a non-orthogonal pad require its contour')
        if quarter % 2:
            width, height = height, width
        x, y = map(float, pad.values[3:5])
        boxes.append(Bounds(x-abs(width)/2, y-abs(height)/2, x+abs(width)/2, y+abs(height)/2))
    for shape, kind, geometry in _pattern_drawings(pattern):
        if kind is None or kind <= 0 or kind == 7 or shape.annotations.get('asc_omit'):
            continue
        points = [point.values[:2] for point in geometry.children('pt')] if geometry else []
        if kind == 6:
            if len(points) != 3:
                raise ValueError(f'{shape.path}: an arc requires three defining points')
            box = circular_arc_bounds(*points)
        else:
            box = Bounds.from_points(points)
        if box:
            boxes.append(box)
    holes = pattern.child('Holes')
    for hole in holes.children('Hole') if holes else ():
        if hole.values[0] not in (True, 'Y'):
            continue
        x, y, diameter = map(float, hole.values[2:5])
        boxes.append(Bounds(x-diameter/2, y-diameter/2, x+diameter/2, y+diameter/2))
    if not boxes:
        return None
    result = boxes[0]
    for box in boxes[1:]:
        result = result.union(box)
    return result


def _pattern_drawings(pattern):
    # Accept our grouped elements and ASC's flat sibling records through
    # one read-only view. The stored tree and original formatting stay intact.
    shapes = pattern.child('Shapes')
    pending = None
    for node in shapes.children() if shapes else ():
        if node.kind == 'Shape':
            if pending:
                yield pending
            kind = node.scalar('Type', node.values[0] if node.values else None)
            pending = node, kind, node.child('Points_New')
        elif node.kind == 'Points_New' and pending:
            pending = pending[0], pending[1], node
    if pending:
        yield pending
