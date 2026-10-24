"""Recognized public content at the semantic import boundary.

This is a field vocabulary check, separate from format layout and geometry.
Unsupported fields remain available in a raw ASC document; converting them to
a binary design must not silently discard them.
"""
from .vocabulary import (COMPONENT_FIELDS, PIN_FIELDS, PATTERN_FIELDS, PAD_FIELDS, SYMBOL_DRAWING_FIELDS, SCHEMATIC_DRAWING_FIELDS, PAGE_FIELDS, SETTINGS_FIELDS, NET_FIELDS, LINE_FIELDS, DIMENSION_FIELDS)
from .vocabulary import (PAGE_CONNECTOR_FIELDS, BUS_FIELDS, BUS_LINE_FIELDS, TABLE_FIELDS, CELL_FIELDS)
from .vocabulary import (CACHED_SYMBOL_FIELDS, CACHED_PIN_FIELDS, CACHED_DRAWING_FIELDS)
from .vocabulary import (SCHEMATIC_FIELDS, PATTERN_DRAWING_FIELDS)
from .traversal import (placed_components, cached_definitions, footprints)


def _known(node, names, *, repeated=()):
    from .definitions import definition
    schema = node.schema or definition(node)
    if node.schema is not None:
        node.schema.validate_parameters(node)
    if schema is not None:
        names = set(names) | schema.fields.keys() | schema.children.keys()
    seen = set()
    for child in node.children():
        if node.schema is not None and child.kind in node.schema.parameters:
            continue
        if child.kind == 'UnresolvedKeys':
            continue
        if child.kind not in names:
            raise ValueError(f'{child.path}: unsupported schematic field')
        if child.kind in seen and child.kind not in repeated:
            raise ValueError(f'{child.path}: duplicate schematic field')
        seen.add(child.kind)


def _rows(node, kind):
    _known(node, (kind,), repeated=(kind,))
    return node.children(kind)


def validate_public_content(document, *, allow_xml_fields=False):
    from .local_keys import (validate_keys)
    from .pad_keys import (public_pad_keys)
    validate_keys(document)
    _known(document.root, ('Source', 'Scale', 'Xpos', 'Ypos', 'Schematic'))
    schematic = document.one('/Schematic')
    _known(schematic, SCHEMATIC_FIELDS)
    from .simulation import (OPTION_FIELDS, ARGUMENT_SCHEMAS)
    simulation = schematic.one('ssimulator')
    _known(simulation, ('tp', 'signals', 'sim_ac', 'sim_dc', 'sim_tran', 'sim_noise',
                        'gndnum', 'gndname', 'sim_digital', *(group for group, *_ in OPTION_FIELDS)))
    for name, definition in ARGUMENT_SCHEMAS.items():
        group = simulation.child(name)
        if group is not None:
            _known(group, (*definition.fields, 'Item'), repeated=('Item',))
    for group in dict.fromkeys(item[0] for item in OPTION_FIELDS):
        options = simulation.child(group)
        if options is not None:
            _known(options, [name for owner, name, *_ in OPTION_FIELDS if owner == group])
    cache = schematic.one('CacheLib')
    _known(cache, ('Categories', 'Subfolders', 'Slots', *(('PatternCategories', 'Patterns', 'PadStyles') if allow_xml_fields else ())))
    for collection in ('Categories', 'PatternCategories'):
        for category in cache.select(collection+'/Category'):
            _known(category, ('Type',), repeated=('Type',))
            for kind in category.children('Type'):
                _known(kind, ('Subtype',), repeated=('Subtype',))
                for subtype in kind.children('Subtype'):
                    _known(subtype, ())
    for slot in _rows(cache.one('Slots'), 'Slot'):
        _known(slot, ('VariablePath', 'Model3DFile_Variable', 'Definition'), repeated=('Definition',))
        for definition in slot.children('Definition'):
            _known(definition, ('Part', 'Pattern'))
    resources = cache.select('Patterns/Pattern') + cache.select('PadStyles/PadStyle')
    if resources and not allow_xml_fields:
        raise ValueError('standalone XML library resources have no field in the schematic DCH format')
    from .vocabulary import PAD_STYLE_FIELDS
    for style in cache.select('PadStyles/PadStyle'):
        _known(style, PAD_STYLE_FIELDS, repeated=('PadTerminal',))
    _known(schematic.one('Settings'), (*SETTINGS_FIELDS, 'NetNameFontSize', 'PartFontMono', *(('MarkingFontName',) if allow_xml_fields else ())))
    for page in _rows(schematic.one('Pages'), 'Page'):
        _known(page, (*PAGE_FIELDS, 'TitleBlocks'))
    symbols = [(part, True) for part in placed_components(schematic)]
    symbols += [(definition.one('Part'), False) for definition in cached_definitions(schematic)]
    for part, placed in symbols:
        _known(part, COMPONENT_FIELDS if placed else (*CACHED_SYMBOL_FIELDS, 'ModelNote', *(('Datasheet',) if allow_xml_fields else ())))
        for pin in _rows(part.one('Pins'), 'Pin'):
            pin_fields = PIN_FIELDS if placed else (*CACHED_PIN_FIELDS, *(('SignalDelay',) if allow_xml_fields else ()))
            _known(pin, (*pin_fields, 'NameFontMono'))
        for shape in _rows(part.one('Shapes'), 'Shape'):
            _known(shape, (*(SYMBOL_DRAWING_FIELDS if placed else CACHED_DRAWING_FIELDS), 'FontMono'))
        _rows(part.one('UserFields'), 'UserField')
        _rows(part.one('ModelBody'), 'Line')
        _known(part.one('Suppliers'), ('PartNumber', 'Manufacturer', 'Pattern', 'Supplier', 'SourceLocator', 'Currency', 'MainSupplier', 'Prices'))
    drawing = PATTERN_DRAWING_FIELDS
    model = '''Model3DFile Model3DFile_Variable Offset Rotate Zoom Mirror NoSearch
Units IPC_XOff IPC_YOff AutoHeight AutoColor Type KeepPins'''.split()
    terminal_fields = 'Type X Y Angle ShapeWidth ShapeHeight ShapeCorner ShapePoints'.split()
    for style in cache.select('PadStyles/PadStyle'):
        for terminal in style.children('PadTerminal'):
            _known(terminal, terminal_fields)
    for pattern in footprints(schematic):
        public_pad_keys(pattern)
        _known(pattern, (*PATTERN_FIELDS, 'PadTerminal', 'Datasheet', *(('Sided', 'RefDes') if allow_xml_fields else ())), repeated=('PadTerminal',))
        _known(pattern.one('Model3D'), model)
        for name in ('Offset', 'Rotate', 'Zoom'):
            _known(pattern.one('Model3D/'+name), ('X', 'Y', 'Z'))
        _rows(pattern.one('UserFields'), 'UserField')
        for pad in _rows(pattern.one('Pads'), 'Pad'):
            _known(pad, (*PAD_FIELDS, 'PadTerminal', 'Id'), repeated=('PadTerminal',))
        for owner in [pattern, *pattern.select('Pads/Pad')]:
            for terminal in owner.children('PadTerminal'):
                _known(terminal, terminal_fields)
        for shape in _rows(pattern.one('Shapes'), 'Shape'):
            _known(shape, drawing)
        for dimension in _rows(pattern.one('Dimensions'), 'Dimension'):
            _known(dimension, (*DIMENSION_FIELDS, 'FontMono'))
    for collection, kind, fields in (
            ('Nets', 'Net', NET_FIELDS), ('Buses', 'Bus', BUS_FIELDS),
            ('Shapes', 'Shape', SCHEMATIC_DRAWING_FIELDS), ('Groups', 'Group', ('Enabled', 'Selected')),
            ('PageConnectors', 'PageConnector', PAGE_CONNECTOR_FIELDS), ('Tables', 'Table', TABLE_FIELDS)):
        for record in _rows(schematic.one(collection), kind):
            extra = {'Shape': ('FontMono', 'PictureFlipped'), 'Table': ('DefFontMono',)}.get(kind, ())
            _known(record, (*fields, *extra))
            if kind in ('Net', 'Bus'):
                for line in _rows(record.one('Lines'), 'Line'):
                    _known(line, LINE_FIELDS if kind == 'Net' else BUS_LINE_FIELDS)
            if kind == 'Table':
                for cell in _rows(record.one('Cells'), 'Cell'):
                    _known(cell, (*CELL_FIELDS, 'FontMono'))

