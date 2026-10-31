"""One current text and angle representation for schematic drawings."""
from ...common.conversion import import_notice


def normalize_drawings(schematic):
    """Discard redundant drawing occurrences after geometry modernization."""
    from .traversal import (symbols)
    anchored = []
    for owner in [schematic, *symbols(schematic)]:
        for shape in owner.select('Shapes/Shape'):
            if owner is schematic and shape.scalar('Type') == 10:
                points = shape.child('Points_New')
                surplus = points.children('pt')[1:] if points is not None else ()
                if surplus:
                    for point in surplus:
                        point.detach()
                    anchored.append(shape)
            for name in ('Name', 'Orientation'):
                field = shape.child(name)
                if field is not None:
                    field.detach()
            stored = shape.child('StoredData')
            if stored is not None:
                for name in ('Name', 'Orientation', 'Type', 'FirstTextLine', 'TextAngleRadians', 'CompatibilityPoints'):
                    for field in stored.children(name):
                        field.detach()
                if not stored.children() and not stored.arguments:
                    stored.detach()
    if anchored:
        import_notice('info', 'sheet-text-anchor',
            'Removed redundant sheet-text bounding points.', anchored,
            recoverability='Text bounds are calculated from the retained anchor, angle and font settings.')
