"""Rebase older placed footprint geometry into its current local coordinates.

The old extra degree rotation was baked into physical coordinates. The current
placement angle owns that rotation, so importing removes it from the local data.
This is import modernization, not a geometric editing/routing operation.
"""
import math

from ....common.geometry import Bounds, transform_point
from ....common.footprint_geometry import legacy_pad_outline
from ....common import footprint_records
from ....common.conversion import import_notice


def _pairs(node, pairs, angle):
    for x, y in pairs:
        if node.child(x) is not None and node.child(y) is not None:
            nx, ny = transform_point((node[x], node[y]), angle=-angle)
            node.set_field(x, nx)
            node.set_field(y, ny)


def _points(collection, angle):
    if collection is not None:
        for point in collection.children('pt'):
            point.set_values(*transform_point(point.values[:2], angle=-angle))


def _contour(pad, angle):
    kind = pad['PadShape_New']
    width, height = float(pad['PadWidth_New']), float(pad['PadHeight_New'])
    if kind in (0, 1) and abs(width-height) <= .02:
        return  # A round pad has no orientation-dependent contour to expand.
    if kind not in (0, 1, 2, 3, 4):
        return
    points = pad.child('PadPoints_New')
    if points is None:
        points = pad.add('PadPoints_New')
    if kind != 3:
        for point in tuple(points.children()):
            point.detach()
        for x, y in legacy_pad_outline(kind, width, height):
            points.add('pt', x, y)
        pad.set_field('PadShape_New', 3)
    _points(points, angle)
    if box := Bounds.from_points(point.values for point in points.children('pt')):
        pad.set_field('PadWidth_New', box.width)
        pad.set_field('PadHeight_New', box.height)


def _drawing(shape, angle, *, half_turn=False):
    points = shape.child('Points_New')
    kind = shape['Type']
    rows = points.children('pt') if points is not None else ()
    if not rows or kind < 1:
        return
    if half_turn and kind == 7:
        shape.set_field('TextAngle', (float(shape['TextAngle'])+math.pi) % math.tau)
        shape.set_field('TextAlign', -shape['TextAlign'])
    circular = (not half_turn and kind in (3, 5) and len(rows) == 2 and
                abs(abs(float(rows[1].values[0])-float(rows[0].values[0]))-
                    abs(float(rows[1].values[1])-float(rows[0].values[1]))) < .3)
    if circular:
        box = Bounds.from_points(row.values for row in rows)
        cx, cy = transform_point(box.center, angle=-angle)
        radius = box.width/2
        rows[0].set_values(cx-radius, cy-radius)
        rows[1].set_values(cx+radius, cy+radius)
    else:
        _points(points, angle)
        if not half_turn and 1 < kind < 6 and len(rows) == 2:
            box = Bounds.from_points(row.values for row in rows)
            rows[0].set_values(box.left, box.top)
            rows[1].set_values(box.right, box.bottom)


def _dimension(dimension, angle, *, extra_rotation=False):
    if dimension.get('Enabled', True):
        if extra_rotation and dimension['Type'] < 2:
            dimension.set_field('Type', 2)
        _pairs(dimension, (('X1', 'Y1'), ('X2', 'Y2'), ('XD', 'YD')), angle)


def rebase_components(decoded):
    """Consume pre-47 placement rotation, leaving source upgrade inputs transient."""
    if decoded.header.version >= 47:
        return
    changed = []
    for item in decoded.upgrades.components:
        component, pattern = item.component, item.component.one('Pattern')
        base_angle = float(component['Angle'])
        quarter = round(base_angle/(math.pi/2))
        degrees = float(item.legacy_field_bindings[2])
        extra = math.radians(degrees)
        half_turn = pattern['Type'] < 14 and component.get('HorizontalFlip', False)
        angle = base_angle+extra+(math.pi if half_turn else 0)
        component.set_field('Angle', angle % math.tau)
        transformed = bool(degrees or half_turn or angle % math.tau != base_angle)

        # Geometry markers and electrical saved keys are distinct format facts.
        # Only an actual interior physical pad participates in this old upgrade.
        pads = [pad for position, pad in enumerate(pattern.select('Pads/Pad')[1:-1], 1)
                if pad['Number_New'] == position]
        for pad in pads:
            pad.bind_schema(footprint_records.PAD)
        shapes = pattern.select('Shapes/Shape')[1:-1]
        holes = pattern.select('Holes/Hole')[1:-1]
        dimensions = pattern.select('Dimensions/Dimension')

        if half_turn:
            component.set_field('Flipped', not component.get('Flipped', False))
            component.set_field('HorizontalFlip', False)
            for pad in pads:
                _pairs(pad, (('X', 'Y'),), math.pi)
                _points(pad.child('PadPoints_New'), math.pi)
                if pad['PadShape_New'] == 4:
                    pad.set_field('PadAngle', (float(pad['PadAngle'])+math.pi) % math.tau)
            for shape in shapes:
                _drawing(shape, math.pi, half_turn=True)
            for hole in holes:
                if hole.values[0]:
                    hole.set_argument(2, -hole.values[2])
                    hole.set_argument(3, -hole.values[3])
            for dimension in dimensions:
                _dimension(dimension, math.pi)
            _pairs(pattern, (('OriginX', 'OriginY'),), math.pi)

        for pad in pads:
            orientation = quarter+round(float(pad['PadAngle'])/(math.pi/2))
            if orientation > 3:
                orientation -= 4
            if pad['PadShape_New'] == 3 and orientation > 1:
                _points(pad.child('PadPoints_New'), math.pi)
                transformed = True

        if abs(degrees) > .001:
            for pad in pads:
                _pairs(pad, (('X', 'Y'),), extra)
                _contour(pad, extra)
            for shape in shapes:
                _drawing(shape, extra)
            for hole in holes:
                if hole.values[0]:
                    x, y = transform_point(hole.values[2:4], angle=-extra)
                    hole.set_argument(2, x)
                    hole.set_argument(3, y)
            for dimension in dimensions:
                _dimension(dimension, extra, extra_rotation=True)
            _pairs(pattern, (('OriginX', 'OriginY'),), extra)
        if transformed:
            changed.append(component)
    if changed:
        import_notice('info', 'legacy-footprint-frame',
                      'Modernized older footprint placement and local geometry.', changed)
