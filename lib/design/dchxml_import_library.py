"""Owned library definitions, independent of their placed instance overrides."""
from dataclasses import dataclass

from .dchxml_import_patterns import read_pattern
from .dchxml_import_pads import read_pad_style
from .dchxml_import_symbols import read_symbol
from .dchxml_import_values import XmlRecord, replace_rows
from .dchxml_units import DchXmlUnits
from .model import Element
from .schematic_objects import new_pattern
from .local_keys import map_key


@dataclass
class ImportedLibrary:
    definitions: dict
    count: int


def _index(record, preferred, default):
    other = 'Number' if preferred == 'Index' else 'Index'
    key = record.integer(preferred, default) if record.has(preferred) else record.integer(other, default)
    if record.has(other):
        alternate = record.integer(other)
        if alternate != key:
            raise ValueError(f'{record.node.path}: conflicting catalog keys')
    return key


def _catalog(record, *, key):
    result = Element('Categories')
    seen = set()
    for index, source in enumerate(record.rows('Categories', 'Category')):
        number = _index(source, key, index)
        if number in seen:
            raise ValueError(f'{source.node.path}: duplicate category key')
        seen.add(number)
        category = result.add('Category', source.text('Name', ''), number)
        type_keys = set()
        for ordinal, item in enumerate(source.rows('Types', 'Type')):
            position = _index(item, key, ordinal)
            if position in type_keys:
                raise ValueError(f'{item.node.path}: duplicate category type key')
            type_keys.add(position)
            kind = category.add('Type', item.text('Name', ''), position)
            subtype_keys = set()
            for order, sub in enumerate(item.rows('SubTypes', 'SubType')):
                value = _index(sub, key, order)
                if value in subtype_keys:
                    raise ValueError(f'{sub.node.path}: duplicate category subtype key')
                subtype_keys.add(value)
                kind.add('Subtype', sub.text('Name', ''), value)
                sub.finish()
            item.finish()
        source.finish()
    return result


def resolve_category(owner, categories):
    prefix = 'Pattern' if owner.kind == 'Pattern' else 'Component'
    key = owner.scalar(prefix+'_CategoryIndex')
    category = next((item for item in categories.children('Category') if item.values[1] == key), None)
    if category is None:
        return
    if not owner.scalar(prefix+'_CategoryName'):
        owner.set_field(prefix+'_CategoryName', category.arguments[0])
    for row in owner.one(prefix+'_CategoryTypes').children():
        kind = next((item for item in category.children('Type') if item.values[1] == row.values[2]), None)
        if kind is None:
            continue
        if not row.values[0]:
            row.set_argument(0, kind.arguments[0])
        subtype = next((item for item in kind.children('Subtype') if item.values[1] == row.values[3]), None)
        if subtype is not None and not row.values[1]:
            row.set_argument(1, subtype.arguments[0])


def _header(record, kind, units):
    if record.text('Type', 'DipTrace-'+kind+'Library') != 'DipTrace-'+kind+'Library':
        raise ValueError(f'{record.node.path}: expected a {kind.lower()} library')
    record.text('Version', '')
    return DchXmlUnits(record.text('Units', units.units))


def read_library(record, schematic, *, units, cache_count):
    if record is None:
        if cache_count:
            raise ValueError('XML cache count requires a component library')
        return ImportedLibrary({}, 0)
    component_units = _header(record, 'Component', units)
    categories = _catalog(record, key='Index')
    pattern_library = record.take('Library', required=True)
    pattern_units = _header(pattern_library, 'Pattern', component_units)
    pattern_categories = _catalog(pattern_library, key='Number')
    styles = {}
    for source in pattern_library.rows('PadStyles', 'PadStyle'):
        key = source.text('Name')
        if key in styles:
            raise ValueError(f'{source.node.path}: duplicate pad style')
        styles[key] = source.node
    patterns, used_styles = {}, set()
    for source in pattern_library.rows('Patterns', 'Pattern'):
        key, data = read_pattern(source, units=pattern_units, styles=styles)
        if key in patterns:
            raise ValueError('duplicate XML pattern style')
        resolve_category(data.element, pattern_categories)
        patterns[key] = data
        used_styles.update(data.used_styles)
    pattern_library.finish()
    cache = schematic.one('CacheLib')
    from .dchxml_pads import PAD_STYLE_FIELDS
    unused_styles = []
    for name, source in styles.items():
        if name not in used_styles:
            style = Element('PadStyle', name)
            for child in new_pattern().children():
                if child.kind in PAD_STYLE_FIELDS:
                    style.append(child.clone())
            read_pad_style(XmlRecord(source), style, units=pattern_units)
            unused_styles.append(style)
    if unused_styles:
        cache.add('PadStyles')
        replace_rows(cache, 'PadStyles', unused_styles)
    replace_rows(cache, 'Categories', [row.clone() for row in categories.children()])
    if pattern_categories.children():
        pattern_categories.kind = 'PatternCategories'
        pattern_categories.annotations['asc_omit'] = 'XML pattern catalog; binary output checks semantic coverage'
        cache.append(pattern_categories)
    slots = cache.one('Slots')
    definitions, used_patterns = {}, set()
    for index, source in enumerate(record.rows('Components', 'Component')):
        key = source.text('ComponentStyle')
        if key in definitions:
            raise ValueError(f'{source.node.path}: duplicate component style')
        slot = slots.add('Slot', index, '')
        slot.add('VariablePath', '')
        variants = []
        for ordinal, item in enumerate(source.children('Part')):
            part, pattern_key, connections = read_symbol(item, units=component_units)
            resolve_category(part, categories)
            if pattern_key is None:
                pattern = new_pattern()
                data = None
            else:
                if pattern_key not in patterns:
                    raise ValueError(f'{item.node.path}: unresolved pattern style {pattern_key!r}')
                used_patterns.add(pattern_key)
                data = patterns[pattern_key]
                pattern = data.element.clone()
            for connection in connections:
                pattern.one('InternalConnections').append(connection)
            if data is not None:
                for connection in connections:
                    for argument, number in enumerate(connection.values):
                        if number >= 0:
                            connection.set_argument(argument, map_key(
                                connection, ('X', 'Y')[argument], number, data.pad_ids))
                for pin in part.select('Pins/Pin') if data.pad_ids and part.scalar('PartType') == 0 else ():
                    number = pin.scalar('Number')
                    pin.set_field('Number', map_key(pin, 'PadId', number, data.pad_ids))
            definition = slot.add('Definition', ordinal)
            definition.append(part)
            definition.append(pattern)
            variants.append(definition)
        if not variants:
            raise ValueError(f'{source.node.path}: a component style needs at least one part')
        source.finish()
        definitions[key] = variants
    record.finish()
    unused_patterns = [data.element for key, data in patterns.items() if key not in used_patterns]
    if unused_patterns:
        cache.add('Patterns')
        replace_rows(cache, 'Patterns', unused_patterns)
    if not 0 <= cache_count <= len(definitions):
        raise ValueError('XML design-cache count exceeds its component definition prefix')
    schematic.set_field('DesignCache_Count', cache_count-1)
    replace_rows(schematic, 'DesignCache_Links', [Element('Link', index) for index in range(cache_count)])
    return ImportedLibrary(definitions, cache_count)
