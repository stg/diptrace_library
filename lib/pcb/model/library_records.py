"""Embedded component definitions have their own scope, separate from placement."""
from dataclasses import replace

from ...common.library_records import CACHE, SLOT, DEFINITION, SLOTS, DESIGN_LINKS
from ...common import symbol_records as symbol
from ...common.drawing_records import POINT, POINTS, TEXT_LINE, TEXT_LINES
from ...common import footprint_records as footprint
from ...common import library_metadata, user_fields
from ...common.schema import Child, Field, Record
from . import internal_connections, local_groups
from .library_relations import DRAWING_PAD_FIELDS


# The shared physical fields have the same meaning. Saved binary pad handles
# are consumed by the importer, while placed PCB pads add electrical membership.
PAD = local_groups.grouped(replace(footprint.PAD, fields={
    name: field for name, field in footprint.PAD.fields.items() if name != 'Number_New'}),
    local_groups.PATTERN_GROUP, name='LibraryPad')
PATTERN_DRAWING = local_groups.grouped(replace(footprint.PATTERN_SHAPE, fields={
    **footprint.PATTERN_SHAPE.fields,
    **DRAWING_PAD_FIELDS,
    'ShieldGroup': Field('ShieldGroup', 'integer', default=-1)}),
    local_groups.PATTERN_GROUP, name='LibraryPatternDrawing')
HOLE = local_groups.grouped(footprint.HOLE, local_groups.PATTERN_GROUP, name='LibraryHole')
DIMENSION = local_groups.grouped(footprint.DIMENSION, local_groups.PATTERN_GROUP, name='LibraryDimension')
PIN = local_groups.grouped(symbol.PIN, local_groups.SYMBOL_GROUP, name='LibraryPin')
DRAWING = local_groups.grouped(symbol.DRAWING, local_groups.SYMBOL_GROUP, name='LibrarySymbolDrawing')
PINS = Record('LibraryPins', {}, children={'Pin': Child('Pin', PIN.name, maximum=None)})
DRAWINGS = Record('LibrarySymbolDrawings', {}, children={'Shape': Child('Shape', DRAWING.name, maximum=None)})
SYMBOL = replace(symbol.SYMBOL, fields={name: field for name, field in symbol.SYMBOL.fields.items()
                                     if name != 'ModelNote'}, children={**symbol.SYMBOL.children,
    'Pins': Child('Pins', PINS.name), 'Shapes': Child('Shapes', DRAWINGS.name),
    'Groups': Child('Groups', local_groups.GROUPS.name)})
PADS = Record('LibraryPads', {}, children={'Pad': Child('Pad', PAD.name, maximum=None)})
CONNECTIONS = Record('LibraryInternalConnections', {}, children={
    'IntCon': Child('IntCon', internal_connections.PAIR.name, maximum=None)})
PATTERN = replace(footprint.PATTERN, fields={**footprint.PATTERN.fields,
    'Value': Field('Value', 'text', description='Default value supplied by an unplaced footprint template.')},
    children={**footprint.PATTERN.children,
    'Pads': Child('Pads', PADS.name), 'InternalConnections': Child('InternalConnections', CONNECTIONS.name),
    'Pattern_Groups': Child('Pattern_Groups', local_groups.GROUPS.name),
    'Holes': Child('Holes', 'LibraryHoles'), 'Shapes': Child('Shapes', 'LibraryPatternDrawings'),
    'Dimensions': Child('Dimensions', 'LibraryDimensions')})

PATTERN_COLLECTIONS = {
    name: Record(record, {}, children={kind: Child(kind, member, maximum=None)})
    for name, record, kind, member in (
        ('Shapes', 'LibraryPatternDrawings', 'Shape', PATTERN_DRAWING.name),
        ('Holes', 'LibraryHoles', 'Hole', HOLE.name),
        ('Dimensions', 'LibraryDimensions', 'Dimension', DIMENSION.name))}
PAD_STYLES = Record('PadStyles', {}, children={'PadStyle': Child('PadStyle', footprint.PAD_STYLE.name, maximum=None)})
PATTERNS = Record('Patterns', {}, children={'Pattern': Child('Pattern', PATTERN.name, maximum=None)})


def is_pattern(node):
    """A physical definition may belong to a component or stand on its own."""
    parent = node.parent
    return (node.kind == 'Pattern' and parent is not None and (
        parent.kind == 'Definition' or parent.kind == 'Patterns' and
        parent.parent is not None and parent.parent.kind == 'CacheLib'))


def patterns(board):
    return (*board.select('CacheLib/Slots/Slot/Definition/Pattern'),
            *board.select('CacheLib/Patterns/Pattern'))


def contains(node):
    """Whether a record belongs to this board's embedded library namespace."""
    current = node
    while current is not None:
        if current.kind == 'CacheLib':
            return current.parent is not None and current.parent.kind == 'Board'
        if current.kind in ('Component', 'Net'):
            return False
        current = current.parent
    return False


def definition(node):
    if (shared := footprint.nested_definition(node)) is not None:
        return shared
    if (metadata := library_metadata.definition(node)) is not None:
        return metadata
    parent = node.parent
    if parent is None:
        return None
    owner = parent.parent
    if node.kind == 'UserFields' and parent.kind == 'Part':
        return user_fields.COMPONENT_USER_FIELDS
    if (node.kind == 'UserField' and parent.kind == 'UserFields' and
            owner is not None and owner.kind == 'Part'):
        return user_fields.COMPONENT_USER_FIELD
    if node.kind == 'CacheLib' and parent.kind == 'Board':
        return CACHE
    if node.kind == 'Slots' and parent.kind == 'CacheLib':
        return SLOTS
    if node.kind == 'Patterns' and parent.kind == 'CacheLib':
        return PATTERNS
    if node.kind == 'PadStyles' and parent.kind == 'CacheLib':
        return PAD_STYLES
    if node.kind == 'PadStyle' and parent.kind == 'PadStyles' and owner is not None and owner.kind == 'CacheLib':
        return footprint.PAD_STYLE
    if node.kind == 'Slot' and parent.kind == 'Slots':
        return SLOT
    if node.kind == 'Definition' and parent.kind == 'Slot':
        return DEFINITION
    if node.kind == 'Part' and parent.kind == 'Definition':
        return SYMBOL
    if is_pattern(node):
        return PATTERN
    pattern = node
    while pattern is not None and pattern.kind != 'Pattern':
        pattern = pattern.parent
    if pattern is not None and is_pattern(pattern):
        if parent is pattern:
            if node.kind == 'Pattern_Groups':
                return local_groups.GROUPS
            if node.kind in PATTERN_COLLECTIONS:
                return PATTERN_COLLECTIONS[node.kind]
            return {'Pads': PADS, 'InternalConnections': CONNECTIONS}.get(node.kind)
        if parent.parent is pattern:
            member = {('Pads', 'Pad'): PAD, ('Shapes', 'Shape'): PATTERN_DRAWING,
                      ('Holes', 'Hole'): HOLE, ('Dimensions', 'Dimension'): DIMENSION,
                      ('Pattern_Groups', 'pt'): local_groups.GROUP,
                      ('InternalConnections', 'IntCon'): internal_connections.PAIR}
            if (schema := member.get((parent.kind, node.kind))) is not None:
                return schema
        if node.kind in ('PadPoints', 'PadPoints_New', 'ShapePoints', 'Points_New'):
            return POINTS
        if node.kind == 'TextLine' and parent.kind == 'Shape':
            return TEXT_LINES
        if node.kind == 'pt':
            return TEXT_LINE if parent.kind == 'TextLine' else POINT if parent.kind in (
                'PadPoints', 'PadPoints_New', 'ShapePoints', 'Points_New') else None
        return None
    if (node.kind == 'Pins' and parent.kind == 'Part' and
            owner is not None and owner.kind == 'Definition'):
        return PINS
    if (node.kind == 'Pin' and parent.kind == 'Pins' and owner is not None and
            owner.kind == 'Part' and owner.parent is not None and owner.parent.kind == 'Definition'):
        return PIN
    symbol = node
    while symbol is not None and symbol.kind != 'Part':
        symbol = symbol.parent
    if symbol is not None and symbol.parent is not None and symbol.parent.kind == 'Definition':
        if node.kind == 'Groups' and parent is symbol:
            return local_groups.GROUPS
        if node.kind == 'pt' and parent.kind == 'Groups' and parent.parent is symbol:
            return local_groups.GROUP
        if node.kind == 'Shapes' and parent is symbol:
            return DRAWINGS
        if node.kind == 'Shape' and parent.parent is symbol:
            return DRAWING
        if parent.kind == 'Shape':
            return {'Points_New': POINTS, 'TextLine': TEXT_LINES}.get(node.kind)
        if node.kind == 'pt':
            return {'Points_New': POINT, 'TextLine': TEXT_LINE}.get(parent.kind)
    return None


def bind_records(board):
    """Establish cached symbol and physical-definition records."""
    for path in ('ProjectLibs_Folders', 'ProjectLibs_Libs', 'DesignCache_Links',
                 'Components/Component/Component_CategoryTypes',
                 'Components/Component/Pattern/Pattern_CategoryTypes',
                 'Components/Component/Pattern/PossibleNames'):
        for root in board.select(path):
            for node in root.walk(include_self=True):
                if (schema := library_metadata.definition(node)) is not None:
                    library_metadata.consume_count(node, schema)
                    node.bind_schema(schema)
    cache = board.child('CacheLib')
    if cache is not None:
        for node in cache.walk(include_self=True):
            if (schema := definition(node)) is not None:
                library_metadata.consume_count(node, schema)
                if schema is DRAWING:
                    # Current text lines and angle supersede the old scalar
                    # label and quarter-turn snapshot, including in newer files.
                    for name in ('Name', 'Orientation'):
                        if (field := node.child(name)) is not None:
                            field.detach()
                node.bind_schema(schema)
                if schema is local_groups.GROUP and (field := node.child('Id')) is not None:
                    field.detach()
                if schema.fields.get('PadTerminalCount') is footprint.TERMINAL_COUNT:
                    if (field := node.child('PadTerminalCount')) is not None:
                        field.detach()
