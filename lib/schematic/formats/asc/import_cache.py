"""Public cl_* cache records into named symbol/footprint definitions."""
from ....common.model import (Element)
from .import_graphics import (unpack_pattern, unpack_symbol_shape)
from .model_body import (unpack_model_body)


def _rename(parent, names):
    for name, target in names.items():
        field = parent.child(name)
        if field is not None:
            field.kind = target


def _categories(owner, prefix):
    _rename(owner, {'CategoryName': prefix+'_CategoryName',
                    'CategoryIndex': prefix+'_CategoryIndex',
                    'CategoryTypes': prefix+'_CategoryTypes'})
    for row in owner.one(prefix+'_CategoryTypes').children():
        if row.kind != 'CategoryType' or row.children() or len(row.arguments) != 4:
            raise ValueError(f'{row.path}: unsupported cached category row')


def _pattern(pattern):
    _categories(pattern, 'Pattern')
    defaults = ('TopMask_State', 'BotMask_State', 'TopPaste_State', 'BotPaste_State',
                'CustomSwell_New', 'CustomShrink_New')
    pads = pattern.select('Pads/Pad')
    for name in defaults:
        values = [pad.children(name)[-1].values for pad in pads]
        if values and any(value != values[0] for value in values[1:]):
            raise ValueError(f'{pattern.path}: conflicting cached footprint default {name}')
        field = pattern.add(name, *(values[0] if values else (-1000 if name.startswith('Custom') else 0,)))
        if not values:
            field.annotations['generated_default'] = 'no pads contain this footprint default in ASC'
        for pad in pads:
            field = pad.children(name)[-1]
            # CustomSwell/Shrink already occur earlier as individual pad data.
            field.detach()
    for pad in pads:
        _rename(pad, {'Point': 'Points'})
    for record in pattern.one('Shapes').children():
        if record.kind == 'Point':
            record.kind = 'Points'
    unpack_pattern(pattern, cached=True)


def _part(part):
    unpack_model_body(part.one('ModelBody'))
    _rename(part, {'OriginX': 'Origin_X', 'OriginY': 'Origin_Y'})
    _categories(part, 'Component')
    for pin in part.select('Pins/Pin'):
        _rename(pin, {'PinNamexShift': 'PinNameXShift'})
    for shape in part.select('Shapes/Shape'):
        _rename(shape, {'Width': 'PenWidth'})
        unpack_symbol_shape(shape)
    part.add('ModelNote', '')
    part.one('Suppliers').add('SourceLocator', '').annotations['asc_omit'] = 'not present in ASC'


def unpack_cache(schematic):
    from ...model.schema import (_known, _rows)
    old = schematic.one('CacheLib')
    for node in old.walk(include_self=True):
        if node.kind.startswith('cl_'):
            node.kind = node.kind[3:]
    _known(old, ('Categories', 'Subfolders', 'Components'))
    categories, folders, components = (old.one(name) for name in ('Categories', 'Subfolders', 'Components'))
    _known(components, ('Component', 'Design_Cache_specific'), repeated=('Component',))
    for container, kind in ((categories, 'Category'), (folders, 'Subfolder')):
        if (len(container.arguments) != 1 or container.arguments[0].kind != 'number'
                or container.arguments[0].unit or container.values[0] != len(container.children(kind))):
            raise ValueError(f'{container.path}: invalid catalog record count')
        container.set_values()
    for category in _rows(categories, 'Category'):
        types = _rows(category, 'Type')
        if len(category.arguments) != 3 or category.values[2] != len(types):
            raise ValueError(f'{category.path}: invalid category type count')
        category.set_values(*category.arguments[:2])
        for kind in types:
            subtypes = _rows(kind, 'SubType')
            if len(kind.arguments) != 3 or kind.values[2] != len(subtypes):
                raise ValueError(f'{kind.path}: invalid category subtype count')
            kind.set_values(*kind.arguments[:2])
            for subtype in subtypes:
                if subtype.children() or len(subtype.arguments) != 2:
                    raise ValueError(f'{subtype.path}: unsupported category subtype')
                subtype.kind = 'Subtype'
    for folder in _rows(folders, 'Subfolder'):
        if folder.children() or len(folder.arguments) != 1:
            raise ValueError(f'{folder.path}: unsupported cache subfolder')
        folder.kind = 'Folder'
    paths = _rows(components.one('Design_Cache_specific'), 'pt')
    definitions = components.children('Component')
    if len(paths) != len(definitions):
        raise ValueError(f'{components.path}: cache path count does not match components')
    cache = Element('CacheLib')
    categories.move_to(cache)
    folders.move_to(cache)
    slots = cache.add('Slots')
    for index, (component, path) in enumerate(zip(definitions, paths)):
        _known(component, ('Part', 'Pattern'), repeated=('Part',))
        if not component.children('Part'):
            raise ValueError(f'{component.path}: cached component has no symbol variants')
        if len(path.arguments) != 2:
            raise ValueError(f'{path.path}: expected actual and variable library paths')
        slot = slots.add('Slot', index, path.arguments[0])
        slot.add('VariablePath', path.arguments[1])
        pattern = component.one('Pattern')
        _pattern(pattern)
        for variant, part in enumerate(component.children('Part')):
            definition = slot.add('Definition', variant)
            part.move_to(definition)
            _part(part)
            definition.append(pattern.clone())
    position = schematic.children().index(old)
    old.detach()
    schematic.insert(cache, position)

