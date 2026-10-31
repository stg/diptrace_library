"""Embedded library definitions, independent of placed PCB instance data."""
from dataclasses import dataclass

from ....common import symbol_objects, footprint_objects
from ....common.conversion import import_notice
from ....common.footprint_records import PAD_STYLE
from ....common.xml_records import XmlRecord
from ....common.xml_symbols import SymbolImportPolicy, read_symbol
from ....common.xml_library_values import read_library_header, read_catalog, resolve_category, read_path, read_subfolders
from ....common.xml_pads import read_pad_style
from .patterns import read_patterns, _key
from .versions import XmlVersion
from ..errors import PcbError
from ...model import library_records


POLICY = SymbolImportPolicy(symbol_objects.new_symbol, symbol_objects.new_pin, symbol_objects.new_drawing, _key)


@dataclass
class ImportedLibrary:
    patterns: dict
    styles: dict
    definitions: tuple


def _unused_styles(cache, styles, used, *, units):
    remaining = [(name, source) for name, source in styles.items() if name not in used]
    if not remaining:
        return
    collection = cache.add('PadStyles')
    defaults = footprint_objects.new_pattern()
    for name, source in remaining:
        style = collection.add('PadStyle', name)
        for child in defaults.children():
            if child.kind != 'Name' and (child.kind in PAD_STYLE.fields or child.kind in PAD_STYLE.children):
                style.append(child.clone())
        read_pad_style(XmlRecord(source), style, units=units)


def _cached_pattern(data):
    pattern = data.element.clone().bind_schema(library_records.PATTERN)
    for name, own in (('RefDes', 'RefDes'), ('Value', 'Value'),
                      ('Manufacturer', 'Pattern_Manufacturer'), ('Datasheet', 'Datasheet')):
        pattern[own] = data.defaults.get(name, '')
    return pattern


def read_library(record, board, *, units, placed_patterns=()):
    cache = board.add('CacheLib')
    slots = cache.add('Slots')
    if record is None:
        cache.add('Categories')
        board.add('DesignCache_Count', -1)
        board.add('DesignCache_Links')
        return ImportedLibrary({}, {}, ())
    physical_width = XmlVersion.parse(record.text('Version','')).physical_font_width
    component_units = read_library_header(record, 'Component', units)
    categories = read_catalog(record, key='Index')
    cache.append(categories)
    if (folders := read_subfolders(record)) is not None:
        cache.append(folders)
    inner = record.take('Library', required=True)
    pattern_units = read_library_header(inner, 'Pattern', component_units)
    pattern_categories = read_catalog(inner, key='Number')
    pattern_categories.kind = 'PatternCategories'
    cache.append(pattern_categories)
    patterns, styles = read_patterns(inner, units=pattern_units)
    inner.finish()
    for data in patterns.values():
        resolve_category(data.element, pattern_categories)
    used_patterns = set()
    definitions = []
    for index, source in enumerate(record.rows('Components', 'Component')):
        if source.has('Id'):
            source.integer('Id')
        if source.has('ComponentStyle'):
            source.text('ComponentStyle')
        slot = slots.add('Slot', index, '')
        slot.add('VariablePath', '')
        paths = []
        parts = source.children('Part')
        primary_data = None
        for ordinal, item in enumerate(parts):
            if (path := item.take('LibPath')) is not None:
                paths.append(read_path(path))
            part, pattern_key, connections = read_symbol(item, units=component_units, policy=POLICY, physical_font_width=physical_width)
            # This empty constructor property has no PCB symbol payload.
            part.one('ModelNote').detach()
            resolve_category(part, categories)
            data = patterns.get(pattern_key) if pattern_key is not None else None
            if pattern_key is not None and data is None:
                raise PcbError(f'{item.node.path}: unresolved footprint style {pattern_key!r}')
            if data is None:
                pattern = None
                if connections:
                    raise PcbError(f'{item.node.path}: internal pad pairs require a physical definition')
            else:
                used_patterns.add(pattern_key)
                pattern = _cached_pattern(data)
            if ordinal == 0:
                primary_data = data
            for connection in connections:
                for argument, number in enumerate(connection.values):
                    if data is not None and number >= 0:
                        connection.set_argument(argument, _key(connection, ('X', 'Y')[argument], number, data.pad_ids))
                pattern.one('InternalConnections').append(connection)
            definition = slot.add('Definition', ordinal)
            definition.append(part)
            if pattern is not None:
                definition.append(pattern)
            definitions.append(definition)
        # A PCB component has one electrical pad domain, supplied by its first
        # part. Secondary parts may omit Pattern or carry independent physical
        # definitions; neither changes the meaning of their Pin.PadId values.
        if primary_data is not None and primary_data.pad_ids:
            for definition in slot.children('Definition'):
                part = definition.one('Part')
                if part['PartType'] == 0:
                    for pin in part.select('Pins/Pin'):
                        number = pin['Number']
                        if number > 0 and number not in primary_data.pad_ids:
                            pin['Number'] = -1
                            import_notice('warning', 'unavailable-symbol-pin-pad',
                                f'Cleared symbol pin assignment to unavailable footprint pad key {number}.',
                                (pin,), recoverability='symbol text and geometry remain; the pin is unassigned')
                        else:
                            pin['Number'] = _key(pin, 'PadId', number, primary_data.pad_ids)
        if paths:
            if any(path != paths[0] for path in paths[1:]):
                raise PcbError(f'{source.node.path}: differing library paths within one component are not mapped')
            slot.set_argument(1, paths[0][0])
            slot.one('VariablePath').set_values(paths[0][1])
        source.finish()
    # Placement consumes geometry, but not the definition's local groups. Keep
    # their template owner if no cached component definition already owns it.
    referenced = used_patterns | set(placed_patterns)
    remaining = [data for key, data in patterns.items()
                 if key not in referenced or key not in used_patterns
                 and data.element.select('Pattern_Groups/pt')]
    if remaining:
        collection = cache.add('Patterns')
        for data in remaining:
            collection.append(_cached_pattern(data))
    _unused_styles(cache, styles, set().union(*(data.used_styles for data in patterns.values())), units=pattern_units)
    record.finish()
    count = len(slots.children('Slot'))
    board.add('DesignCache_Count', count-1)
    links = board.add('DesignCache_Links')
    for index in range(count):
        links.add('Link', index)
    return ImportedLibrary(patterns, styles, tuple(definitions))
