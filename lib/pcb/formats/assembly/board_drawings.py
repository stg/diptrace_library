"""Discard filled board primitives that do not describe usable filled geometry."""
from decimal import Decimal

from ....common.conversion import import_notice
from ....common.geometry import Bounds


MIN_FILLED_SPAN = Decimal('0.0001')


def disable_degenerate_drawings(board):
    """Mark unusable input drawings for ordinary identity-aware compaction.

    Rectangle/ellipse corners define their two spans. Polygon input has only
    the established two-point rejection; this is not a polygon-area algorithm.
    """
    removed = []
    for drawing in board.select('Shapes/Shape'):
        if not drawing.get('Enabled', True):
            continue
        kind = drawing.get('Type', 0)
        if kind not in (3, 5, 9):
            continue
        points = drawing.child('Points')
        if points is None:
            points = drawing.child('Points_New')
        vertices = points.children('pt') if points is not None else ()
        if len(vertices) < 2:
            continue
        if kind == 9:
            degenerate = len(vertices) == 2
        else:
            x1, y1 = vertices[0].values[:2]
            x2, y2 = vertices[1].values[:2]
            bounds = Bounds(x1, y1, x2, y2)
            degenerate = any(-MIN_FILLED_SPAN < span < MIN_FILLED_SPAN
                             for span in (bounds.width, bounds.height))
        if degenerate:
            drawing.set_field('Enabled', False)
            removed.append(drawing)
    if removed:
        import_notice('info', 'degenerate-board-drawing',
                      'Removed degenerate filled board drawings.', removed,
                      recoverability='unusable filled primitives are omitted; other drawing geometry remains')
    return tuple(removed)
