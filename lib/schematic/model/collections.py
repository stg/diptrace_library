"""Owned collection definitions, independent of serialized count headers."""
from ...common.schema import Child, Field, Record


def collection(name, kind, record):
    return Record(name, {}, description='An ordered collection of '+record+' records.',
                  children={kind: Child(kind, record, maximum=None)})


CLASSIFICATIONS = collection('Classifications', 'CategoryType', 'CategoryType')
POSSIBLE_NAMES = collection('PossibleNames', 'PossibleName', 'PossibleName')
PASTE_SEGMENTS = collection('PasteSegments', 'pt', 'PasteSegment')
PROJECT_FOLDERS = collection('ProjectFolders', 'Folder', 'LibraryPath')
PROJECT_LIBRARIES = collection('ProjectLibraries', 'Lib', 'LibraryPath')
DESIGN_LINKS = collection('DesignCacheLinks', 'Link', 'DesignCacheLink')
DESIGN_LINK = Record('DesignCacheLink', {
    'SlotIndex': Field('SlotIndex', 'integer', required=True, default=-1,
                       description='Managed library-slot index in the active prefix; a literal capacity value beyond it.'),
}, ('SlotIndex',))


# Collection names describe their contents; tree names remain the public names.
COLLECTIONS = {
    name: collection(name, kind, record) for name, kind, record in (
        ('Pages', 'Page', 'Page'), ('Components', 'Part', 'Part'),
        ('Nets', 'Net', 'Net'), ('Buses', 'Bus', 'Bus'),
        ('PageConnectors', 'PageConnector', 'PageConnector'),
        ('Tables', 'Table', 'Table'), ('NetClasses', 'NetClass', 'NetClass'),
        ('DifferentialPairs', 'DifferentialPair', 'DifferentialPair'),
        ('Pins', 'Pin', 'Pin'), ('CachedPins', 'Pin', 'CachedPin'),
        ('SymbolDrawings', 'Shape', 'SymbolDrawing'), ('SheetDrawings', 'Shape', 'SheetDrawing'),
        ('PatternDrawings', 'Shape', 'PatternDrawing'), ('Pads', 'Pad', 'Pad'),
        ('Holes', 'Hole', 'Hole'), ('Dimensions', 'Dimension', 'Dimension'),
        ('UserFields', 'UserField', 'UserField'), ('ComponentUserFields', 'UserField', 'ComponentUserField'),
        ('ModelBody', 'Line', 'ModelLine'), ('TextLines', 'pt', 'TextLine'),
        ('Points', 'pt', 'Point'), ('WirePoints', 'pt', 'WirePoint'),
        ('Wires', 'Line', 'Wire'), ('BusWires', 'Line', 'BusWire'),
        ('NetMembers', 'pt', 'NetMember|UnresolvedNetMember'),
        ('BusNets', 'pt', 'BusNet'), ('BusNumbers', 'pt', 'BusNumber'), ('LocalGroups', 'pt', 'LocalGroup'),
        ('SchematicGroups', 'Group', 'SchematicGroup'), ('Slots', 'Slot', 'LibrarySlot'),
        ('Patterns', 'Pattern', 'Pattern'), ('PadStyles', 'PadStyle', 'PadStyle'),
        ('Categories', 'Category', 'CatalogCategory'), ('Subfolders', 'Folder', 'LibrarySubfolder'),
        ('InternalConnections', 'IntCon', 'InternalConnection'), ('Prices', 'Quote', 'Quote'),
        ('Signals', 'signal', 'SimulationSignal'), ('ColumnWidths', 'pt', 'ColumnWidth'),
        ('RowHeights', 'pt', 'RowHeight'), ('TableCells', 'Cell', 'Cell'),
        ('TitleCells', 'Cell', 'TitleCell'), ('TitleFields', 'Content', 'TitleField'),
        ('GlobalUserFields', 'pt', 'GlobalUserField'), ('UnresolvedKeys', 'Key', 'UnresolvedKey'),
    )
}
COLLECTIONS['TitleBlocks'] = Record('TitleBlocks', {}, children={
    'TitleBlock': Child('TitleBlock', 'TitleBlock', maximum=6),
})


def _collection(node):
    parent = node.parent
    if parent is None:
        return None
    name, owner = node.kind, parent.kind
    if name in ('TextLine', 'Points_New', 'PadPoints', 'PadPoints_New', 'ShapePoints', 'Points'):
        key = 'TextLines' if name == 'TextLine' else 'WirePoints' if owner == 'Line' else 'Points'
    elif name == 'Pins' and owner == 'Part':
        key = 'Pins' if parent.parent is not None and parent.parent.kind == 'Components' else 'CachedPins'
    elif name == 'Shapes':
        key = {'Part': 'SymbolDrawings', 'Pattern': 'PatternDrawings', 'Schematic': 'SheetDrawings'}.get(owner)
    elif name == 'UserFields':
        key = 'ComponentUserFields' if owner == 'Part' else 'UserFields'
    elif name == 'Lines':
        key = 'Wires' if owner == 'Net' else 'BusWires' if owner == 'Bus' else None
    elif name == 'Groups':
        key = 'SchematicGroups' if owner == 'Schematic' else 'LocalGroups'
    elif name == 'Pattern_Groups':
        key = 'LocalGroups'
    elif name == 'Parts' and owner == 'Net':
        key = 'NetMembers'
    elif name == 'Nets' and owner == 'Bus':
        key = 'BusNets'
    elif name == 'Numbers' and owner == 'Bus':
        key = 'BusNumbers'
    elif name == 'Cells':
        key = 'TitleCells' if owner == 'TitleBlock' else 'TableCells'
    else:
        key = {'ColWidths': 'ColumnWidths', 'RowHeights': 'RowHeights', 'Contents': 'TitleFields',
               'ShowUserfield_Global': 'GlobalUserFields', 'signals': 'Signals',
               'PatternCategories': 'Categories'}.get(name, name)
    return COLLECTIONS.get(key)


# These headers contain only serialized row counts. DesignCache_Count itself is
# a separate last-active index and is deliberately not part of this mapping.
COUNTED_COLLECTIONS = {
    'Component_CategoryTypes': (frozenset(('Part',)), CLASSIFICATIONS),
    'Pattern_CategoryTypes': (frozenset(('Pattern',)), CLASSIFICATIONS),
    'PossibleNames': (frozenset(('Pattern',)), POSSIBLE_NAMES),
    'PadMask_TopSegments': (frozenset(('Pad', 'Pattern', 'PadStyle')), PASTE_SEGMENTS),
    'PadMask_BotSegments': (frozenset(('Pad', 'Pattern', 'PadStyle')), PASTE_SEGMENTS),
    'ProjectLibs_Folders': (frozenset(('Schematic',)), PROJECT_FOLDERS),
    'ProjectLibs_Libs': (frozenset(('Schematic',)), PROJECT_LIBRARIES),
    'DesignCache_Links': (frozenset(('Schematic',)), DESIGN_LINKS),
}


def definition(node):
    rule = COUNTED_COLLECTIONS.get(node.kind)
    if rule and node.parent is not None and node.parent.kind in rule[0]:
        return rule[1]
    return _collection(node)
