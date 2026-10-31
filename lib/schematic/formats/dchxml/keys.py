"""Public XML key namespaces, including records with no incoming links."""
from ....common.references import (ReferenceError)


def _rows(owner, container, kind):
    group = owner.child(container) if owner is not None else None
    return group.children(kind) if group is not None else []


def keyspaces(document):
    source = document.root.child('Source')
    library = source.child('Library') if source is not None else None
    patterns = library.child('Library') if library is not None else None
    for owner, container, kind, key in (
            (library, 'Components', 'Component', 'ComponentStyle'),
            (patterns, 'Patterns', 'Pattern', 'PatternStyle'),
            (patterns, 'PadStyles', 'PadStyle', 'Name')):
        if owner is not None and owner.child(container) is not None:
            yield owner.one(container), kind, key
    for pattern in _rows(patterns, 'Patterns', 'Pattern'):
        for container, kind in (('Pads', 'Pad'), ('Shapes', 'Shape'), ('Holes', 'Hole'), ('Groups', 'Item')):
            if pattern.child(container) is not None:
                yield pattern.one(container), kind, 'Id'
    for component in _rows(library, 'Components', 'Component'):
        for part in component.children('Part'):
            if part.child('Groups') is not None:
                yield part.one('Groups'), 'Item', 'Id'
    for owner, key in ((library, 'Index'), (patterns, 'Number')):
        if owner is None:
            continue
        if owner.child('Categories') is not None:
            yield owner.one('Categories'), 'Category', key
        for category in _rows(owner, 'Categories', 'Category'):
            if category.child('Types') is not None:
                yield category.one('Types'), 'Type', key
            for item in _rows(category, 'Types', 'Type'):
                if item.child('SubTypes') is not None:
                    yield item.one('SubTypes'), 'SubType', key
    schematic = source.child('Schematic') if source is not None else None
    if schematic is None:
        return
    for container, kind in (('Components', 'Part'), ('Nets', 'Net'), ('Buses', 'Bus'),
                             ('BusConnectors', 'BusConnector'), ('Groups', 'Group'),
                             ('NetClasses', 'NetClass'), ('Shapes', 'Shape'), ('Tables', 'Table')):
        if schematic.child(container) is not None:
            yield schematic.one(container), kind, 'Id'
    for container, kind in (('Nets', 'Net'), ('Buses', 'Bus')):
        for item in _rows(schematic, container, kind):
            if item.child('Wires') is not None:
                yield item.one('Wires'), 'Wire', 'Id'
    settings = schematic.child('SheetSettings')
    if settings is not None and settings.child('Sheets') is not None:
        yield settings.one('Sheets'), 'Sheet', 'Id'
    from ....common.title_records import TITLE_BLOCKS
    for sheet in _rows(settings, 'Sheets', 'Sheet'):
        for name in TITLE_BLOCKS:
            for block in sheet.children(name):
                if block.child('Fields') is not None:
                    yield block.one('Fields'), 'Field', 'Id'


def validate_keys(document):
    for owner, kind, name in keyspaces(document):
        seen = set()
        for item in owner.children(kind):
            fields = item.children(name)
            if not fields:
                continue  # A raw/partial record need not declare this key.
            if len(fields) != 1 or len(fields[0].arguments) != 1:
                raise ReferenceError(f'{item.path}: expected one scalar XML key {name}')
            expected = 'string' if name in ('Name', 'PatternStyle', 'ComponentStyle') else 'number'
            if fields[0].arguments[0].kind != expected:
                raise ReferenceError(f'{item.path}: XML key {name} requires a {expected} value')
            key = fields[0].values[0]
            if key in seen:
                raise ReferenceError(f'{owner.path}: duplicate XML {name} key {key!r}')
            seen.add(key)
