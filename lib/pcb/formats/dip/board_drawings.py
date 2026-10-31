"""Resolve earlier board drawing rectangles into current authored geometry."""
from decimal import Decimal
import math

from ....common.conversion import import_notice
from ....common.geometry import Bounds, ellipse_points, unequal_extents


def modernize_board_drawings(decoded):
    """Upgrade the old DIP drawing domain without retaining its spare corners.

    Board drawing types differ from footprint/symbol drawing types. Their
    geometry shares ordinary anchor and ellipse operations, but their version
    gate and interpretation stay with this adapter.
    """
    version = decoded.header.version
    if version >= 50:
        return
    changed = []
    for item in getattr(decoded.upgrades, 'drawings', ()):
        shape = item.drawing
        updated = False
        if version < 47 and shape.child('TextAngle') is None:
            _geometry(shape, item.orientation)
            updated = True
        for name, value in {'PictureRaster': False, 'Picture_File': '', 'PictureTransparent': 0}.items():
            if shape.child(name) is None:
                shape.add(name, value)
                updated = True
        if updated:
            changed.append(shape)
    if changed:
        import_notice('info', 'legacy-board-drawing', 'Modernized earlier board drawing data.', changed)


def _geometry(shape, old_orientation):
    kind = shape['Type']
    geometry = shape.one('Points')
    rows = geometry.children('pt')
    angle = old_orientation * math.pi / 2
    width = height = 0
    if kind == 7 and len(rows) > 1:
        # Earlier pictures save an unoriented rectangle. Current data has
        # a top-left anchor and explicit dimensions, independent of which
        # diagonal was used to draw the rectangle.
        first, opposite = (row.values for row in rows[:2])
        box = Bounds(min(first[0], opposite[0]), min(first[1], opposite[1]),
                     max(first[0], opposite[0]), max(first[1], opposite[1]))
        width, height = box.width, box.height
        rows[0].set_values(box.left, box.top)
        rows[1].set_values(box.right, box.bottom)
        orientation, angle = 0, 0
    else:
        orientation = old_orientation
    if kind in (6, 7) and len(rows) > 1:
        first, opposite = (row.arguments for row in rows[:2])
        corners = (first, (first[0], opposite[1]), opposite, (opposite[0], first[1]))
        anchor = corners[orientation] if 0 <= orientation < 4 else first
        rows[0].set_values(*anchor)
        for row in rows[1:]:
            row.detach()
    elif kind in (4, 5) and len(rows) >= 2:
        first, opposite = (row.values for row in rows[:2])
        if unequal_extents(first, opposite, tolerance='.3'):
            points = ellipse_points(first, opposite, segments=30, closed=kind == 4)
            for row in rows:
                row.detach()
            for point in points:
                geometry.add('pt', *point)
            shape.set_field('Type', 8 if kind == 4 else 9)
    for name, value in {'TextAngle': angle, 'TextHorz': -1, 'TextVert': -1,
                        'TextAlign': -1, 'LineSpacing': Decimal('1.2'),
                        'PictureWidth': width, 'PictureHeight': height,
                        'PictureProportions': False, 'Inverted': False}.items():
        shape.set_field(name, value)
