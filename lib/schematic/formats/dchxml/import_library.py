"""Owned library definitions, independent of their placed instance overrides."""
from dataclasses import dataclass

from .import_patterns import (read_pattern)
from ....common.xml_pads import (read_pad_style)
from .import_symbols import (read_symbol)
from ....common.xml_records import XmlRecord, replace_rows, application_version
from ....common.font_codec import PHYSICAL_XML_WIDTH_SINCE
from ....common.model import (Element)
from ....common.xml_library_values import read_catalog as _catalog, read_library_header as _header, resolve_category, read_subfolders
from ...model.objects import (new_pattern)
from ...model.local_keys import (map_key)


@dataclass
class ImportedLibrary:
    definitions: dict
    count: int


def read_library(record, schematic, *, units, cache_count):
    if record is None:
        if cache_count:
            raise ValueError('XML cache count requires a component library')
        return ImportedLibrary({}, 0)
    component_width = application_version(record.text('Version',''),default=PHYSICAL_XML_WIDTH_SINCE) >= PHYSICAL_XML_WIDTH_SINCE
    component_units = _header(record, 'Component', units)
    categories = _catalog(record, key='Index')
    pattern_library = record.take('Library', required=True)
    pattern_width = application_version(pattern_library.text('Version',''),default=PHYSICAL_XML_WIDTH_SINCE) >= PHYSICAL_XML_WIDTH_SINCE
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
        key, data = read_pattern(source, units=pattern_units, styles=styles, physical_font_width=pattern_width)
        if key in patterns:
            raise ValueError('duplicate XML pattern style')
        resolve_category(data.element, pattern_categories)
        patterns[key] = data
        used_styles.update(data.used_styles)
    pattern_library.finish()
    cache = schematic.one('CacheLib')
    if (folders := read_subfolders(record)) is not None:
        replace_rows(cache, 'Subfolders', [row.clone() for row in folders.children()])
    from ...model.vocabulary import PAD_STYLE_FIELDS
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
        source.integer('Id', index)
        key = source.text('ComponentStyle')
        if key in definitions:
            raise ValueError(f'{source.node.path}: duplicate component style')
        slot = slots.add('Slot', index, '')
        slot.add('VariablePath', '')
        variants = []
        for ordinal, item in enumerate(source.children('Part')):
            part, pattern_key, connections = read_symbol(item, units=component_units, physical_font_width=component_width)
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
