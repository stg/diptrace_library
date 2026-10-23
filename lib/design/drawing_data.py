"""One current text and angle representation for schematic drawings."""


def normalize_drawings(schematic):
    """Discard redundant drawing occurrences after geometry modernization."""
    from .dch_records import symbols
    for owner in [schematic, *symbols(schematic)]:
        for shape in owner.select('Shapes/Shape'):
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
