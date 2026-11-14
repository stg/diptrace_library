"""Shared project-library settings, catalogues and embedded definitions."""
from dataclasses import dataclass
from typing import Callable

from .model import Element, SourceSpan
from .catalog_codec import read_categories, read_category_types, read_possible_names, write_category_types
from .symbol_codec import (read_cached_pins, write_cached_pins,
                           read_symbol_parameters, write_symbol_parameters)


@dataclass(frozen=True)
class LibraryCodecs:
    pattern_parameters: Callable
    pattern_pads: Callable
    pattern_graphics: Callable
    pattern_model: Callable
    symbol_graphics: Callable
    definition_text: str


@dataclass(frozen=True)
class CachedDefinitionInput:
    definition: Element
    pattern_inputs: object


def _user_fields(r, parent, *, symbol=False):
    fields = r.add(parent, "UserFields")
    for _ in range(r.count("cached user fields")):
        node = r.add(fields, "UserField", r.argument('text'), r.argument('text'), r.argument('integer'))
        if symbol:
            # Cached symbol label choices are zero-initialized and absent from
            # the binary record, but ASC cl_UserField emits their seven values.
            node.set_values(*node.arguments, *(0 for _ in range(7)))



def discard_legacy_groups(r, member_kinds):
    """Consume obsolete member lists; current groups have their own extension."""
    for _ in range(r.count("obsolete cached groups")):
        r.boolean()
        r.integer()
        for _ in member_kinds:
            for _ in range(r.count("group members")):
                r.integer()


def read_definition(r, slot, variant, codecs):
    start = r.pos
    definition = r.add(slot, "Definition", variant)
    part = r.add(definition, "Part")
    read_symbol_parameters(r, part)
    pattern = r.add(definition, "Pattern")
    connections = r.add(pattern, "InternalConnections")
    for _ in range(r.count("cached internal connections")):
        r.add_into(connections, "IntCon", r.argument('integer'), r.argument('integer'))
    codecs.pattern_parameters(r, pattern)
    for name in ("Origin_X", "Origin_Y"):
        r.field_into(part, name, "number")
    points = r.add(pattern, "PadPoints")
    for _ in range(r.count("cached default pad points")):
        r.add_into(points, "pt", r.argument('number'), r.argument('number'))
    pad_count = r.count("cached pads")
    # Cache ASC emits the reserved records as well (unlike placed footprints).
    codecs.pattern_pads(r, pattern, count=pad_count)
    pattern_inputs = codecs.pattern_graphics(r, pattern)
    discard_legacy_groups(r, ("Pads", "Shapes", "Holes"))
    _user_fields(r, pattern)
    codecs.pattern_model(r, pattern)
    r.field_into(pattern.child('Model3D'), 'Units', 'integer')
    r.field_into(pattern, "Mounting", "integer")
    r.field_into(pattern, "Pattern_CategoryName", "text")
    r.field_into(pattern, "Pattern_CategoryIndex", "integer")
    read_category_types(r, pattern, "Pattern_CategoryTypes")
    read_possible_names(r, pattern)
    read_cached_pins(r, part)
    shape_count = r.count("cached symbol shapes")
    codecs.symbol_graphics(r, part, count=shape_count)
    discard_legacy_groups(r, ("Pins", "Shapes"))
    _user_fields(r, part, symbol=True)
    r.field_into(part, "ModelType", "integer")
    # Cache text uses the document version's ordinary string encoding.
    r.field_into(part, "ModelString", "text")
    body = r.add(part, "ModelBody")
    for _ in range(r.count("cached model lines")):
        r.add_into(body, "Line", r.argument('text'))
    r.field_into(part, "SubfolderIndex", "integer")
    count = r.count('verification flags')
    flags = r.record(part, 'Verification', *('boolean',)*count)
    flags.set_values(*((flags.arguments + (False,) * 7)[:7]))
    # The wire position is shared, but its meaning belongs to the document
    # family: a schematic model note and a PCB datasheet are distinct facts.
    r.field_into(part, codecs.definition_text, 'text')
    r.field_into(part, "Manufacturer", "text")
    r.field_into(part, "Component_CategoryName", "text")
    r.field_into(part, "Component_CategoryIndex", "integer")
    read_category_types(r, part, "Component_CategoryTypes")
    definition.source = SourceSpan(r.source_format, start, r.pos, r.source)
    part.annotations["incomplete"] = "later cached-symbol extensions and ASC projection remain"
    definition.annotations["incomplete"] = "later cache extensions and ASC projection remain"
    return CachedDefinitionInput(definition, pattern_inputs)


def read_library_cache(r, owner, codecs):
    inputs = []
    for kind, name in [("text", "ProjectLibs_Name"), ("integer", "ProjectLibs_Type"),
                       ("integer", "ProjectLibs_Content")]:
        r.field_into(owner, name, kind)
    for name, child in (("ProjectLibs_Folders", "Folder"), ("ProjectLibs_Libs", "Lib")):
        count = r.count(name)
        paths = r.add(owner, name, count)
        for _ in range(count):
            r.add_into(paths, child, r.argument('text'))
    r.field_into(owner, "ProjectLibs_Sorted", "boolean")
    r.field_into(owner, "DesignCache_Count", "integer")
    count = r.count("cache links")
    links = r.add(owner, "DesignCache_Links", count)
    for _ in range(count):
        r.add_into(links, "Link", r.argument('integer'))
    cache = r.add(owner, "CacheLib")
    read_categories(r, cache)
    folders = r.add(cache, "Subfolders")
    for _ in range(r.count("cache subfolders")):
        r.add_into(folders, "Folder", r.argument('text'))
    slots = r.add(cache, "Slots")
    for index in range(r.count("cache slots")):
        slot = r.add(slots, "Slot", index)
        for variant in range(r.count("cache slot variants")):
            inputs.append(read_definition(r, slot, variant, codecs))
    for slot in slots.children("Slot"):
        slot.set_values(slot.values[0], r.argument('text'))
    cache.annotations["incomplete"] = "later cache extensions and ASC projection remain"
    return tuple(inputs)


def write_definition(writer, definition, codecs):
    """Shared definition envelope with family-owned physical/symbol codecs."""
    part, pattern = definition.one('Part'), definition.one('Pattern')
    write_symbol_parameters(writer, part)
    writer.rows(pattern.child('InternalConnections'), 'IntCon', 'integer integer')
    codecs.pattern_parameters(writer, pattern)
    writer.fields(part, 'number', 'Origin_X Origin_Y')
    writer.rows(pattern.child('PadPoints'), 'pt', 'number number')
    codecs.pattern_pads(writer, pattern)
    codecs.pattern_graphics(writer, pattern)
    writer.integer(0)  # Current groups have their own later extension.
    writer.rows(pattern.child('UserFields'), 'UserField', 'text text integer')
    codecs.pattern_model(writer, pattern)
    writer.field(pattern.one('Model3D'), 'Units', 'integer')
    writer.field(pattern, 'Mounting', 'integer')
    writer.field(pattern, 'Pattern_CategoryName', 'text')
    writer.field(pattern, 'Pattern_CategoryIndex', 'integer')
    write_category_types(writer, pattern, 'Pattern_CategoryTypes')
    writer.rows(pattern.child('PossibleNames'), 'PossibleName', 'text')
    write_cached_pins(writer, part)
    codecs.symbol_graphics(writer, part)
    writer.integer(0)
    writer.rows(part.child('UserFields'), 'UserField', 'text text integer', trailing=7)
    writer.field(part, 'ModelType', 'integer')
    writer.field(part, 'ModelString', 'text')
    writer.rows(part.child('ModelBody'), 'Line', 'text')
    writer.field(part, 'SubfolderIndex', 'integer')
    writer.integer(7)
    for flag in part['Verification']:
        writer.boolean(flag)
    writer.text(part.get(codecs.definition_text, ''))
    writer.field(part, 'Manufacturer', 'text')
    writer.field(part, 'Component_CategoryName', 'text')
    writer.field(part, 'Component_CategoryIndex', 'integer')
    write_category_types(writer, part, 'Component_CategoryTypes')


def write_library_cache(writer, owner, definition_writer):
    writer.field(owner, 'ProjectLibs_Name', 'text')
    writer.fields(owner, 'integer', 'ProjectLibs_Type ProjectLibs_Content')
    writer.rows(owner.child('ProjectLibs_Folders'), 'Folder', 'text')
    writer.rows(owner.child('ProjectLibs_Libs'), 'Lib', 'text')
    writer.field(owner, 'ProjectLibs_Sorted', 'boolean')
    writer.field(owner, 'DesignCache_Count', 'integer')
    writer.rows(owner.child('DesignCache_Links'), 'Link', 'integer')
    write_cache_library(writer, owner.child('CacheLib'), definition_writer)


def write_cache_library(writer, cache, definition_writer):
    """Catalogues and definitions following the caller's project settings."""
    categories = cache.select('Categories/Category') if cache is not None else ()
    writer.integer(len(categories))
    for category in categories:
        writer.field(category, 'Name', 'text')
        writer.field(category, 'Index', 'integer')
        types = category.children('Type')
        writer.integer(len(types))
        for kind in types:
            writer.field(kind, 'Name', 'text')
            writer.field(kind, 'Index', 'integer')
            writer.rows(kind, 'Subtype', 'text integer')
    writer.rows(cache.child('Subfolders') if cache is not None else None, 'Folder', 'text')
    slots = cache.select('Slots/Slot') if cache is not None else ()
    writer.integer(len(slots))
    for slot in slots:
        definitions = slot.children('Definition')
        writer.integer(len(definitions))
        for definition in definitions:
            definition_writer(writer, definition)
    for slot in slots:
        writer.field(slot, 'LibPath', 'text')
