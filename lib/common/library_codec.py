"""Shared project-library settings, catalogues and embedded definitions."""
from dataclasses import dataclass
from typing import Callable

from .model import Element, SourceSpan
from .catalog_codec import read_category_types, read_possible_names, write_category_types
from .symbol_codec import read_cached_pins, write_cached_pins


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
    fields = parent.add("UserFields")
    for _ in range(r.count("cached user fields")):
        node = fields.add("UserField", r.argument('text'), r.argument('text'), r.argument('integer'))
        if symbol:
            # Cached symbol label choices are zero-initialized and absent from
            # the binary record, but ASC cl_UserField emits their seven values.
            node.set_values(*node.arguments, *(0 for _ in range(7)))
            node.annotations['label_defaults_for_version'] = r.header.version


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
    definition = slot.add("Definition", variant)
    part = definition.add("Part")
    for kind, name in [("boolean", "Enabled"), ("integer", "PartType"),
                       ("text", "PartName"), ("integer", "ShowNumbers"),
                       ("integer", "Type"), ("integer", "Number1"), ("integer", "Number2"),
                       ("number", "Width"), ("number", "Height")]:
        r.field(part, name, kind)
    part.set_values(r.argument('text'), r.argument('text'))
    r.field(part, "Value", "text")
    r.field(part, "LockProperties", "boolean")
    pattern = definition.add("Pattern")
    connections = pattern.add("InternalConnections")
    for _ in range(r.count("cached internal connections")):
        connections.add("IntCon", r.argument('integer'), r.argument('integer'))
    codecs.pattern_parameters(r, pattern)
    for name in ("Origin_X", "Origin_Y"):
        r.field(part, name, "number")
    points = pattern.add("PadPoints")
    for _ in range(r.count("cached default pad points")):
        points.add("pt", r.argument('number'), r.argument('number'))
    pattern.annotations["declared_pad_count"] = r.count("cached pads")
    # Cache ASC emits the reserved records as well (unlike placed footprints).
    codecs.pattern_pads(r, pattern)
    pattern_inputs = codecs.pattern_graphics(r, pattern)
    discard_legacy_groups(r, ("Pads", "Shapes", "Holes"))
    _user_fields(r, pattern)
    codecs.pattern_model(r, pattern)
    r.field(pattern.child('Model3D'), 'Units', 'integer')
    r.field(pattern, "Mounting", "integer")
    r.field(pattern, "Pattern_CategoryName", "text")
    r.field(pattern, "Pattern_CategoryIndex", "integer")
    read_category_types(r, pattern, "Pattern_CategoryTypes")
    read_possible_names(r, pattern)
    read_cached_pins(r, part)
    part.annotations["declared_shape_count"] = r.count("cached symbol shapes")
    codecs.symbol_graphics(r, part)
    discard_legacy_groups(r, ("Pins", "Shapes"))
    _user_fields(r, part, symbol=True)
    r.field(part, "ModelType", "integer")
    # Cache text uses the document version's ordinary string encoding.
    r.field(part, "ModelString", "text")
    body = part.add("ModelBody")
    for _ in range(r.count("cached model lines")):
        body.add("Line", r.argument('text'))
    r.field(part, "SubfolderIndex", "integer")
    count = r.count('verification flags')
    flags = r.record(part, 'Verification', *('boolean',)*count)
    flags.set_values(*((flags.arguments + (False,) * 7)[:7]))
    # The wire position is shared, but its meaning belongs to the document
    # family: a schematic model note and a PCB datasheet are distinct facts.
    r.field(part, codecs.definition_text, 'text')
    r.field(part, "Manufacturer", "text")
    r.field(part, "Component_CategoryName", "text")
    r.field(part, "Component_CategoryIndex", "integer")
    read_category_types(r, part, "Component_CategoryTypes")
    definition.source = SourceSpan(r.source_format, start, r.pos, r.source)
    part.annotations["incomplete"] = "later cached-symbol extensions and ASC projection remain"
    definition.annotations["incomplete"] = "later cache extensions and ASC projection remain"
    return CachedDefinitionInput(definition, pattern_inputs)


def read_library_cache(r, owner, codecs):
    inputs = []
    for kind, name in [("text", "ProjectLibs_Name"), ("integer", "ProjectLibs_Type"),
                       ("integer", "ProjectLibs_Content")]:
        r.field(owner, name, kind)
    for name, child in (("ProjectLibs_Folders", "Folder"), ("ProjectLibs_Libs", "Lib")):
        count = r.count(name)
        paths = owner.add(name, count)
        for _ in range(count):
            paths.add(child, r.argument('text'))
    r.field(owner, "ProjectLibs_Sorted", "boolean")
    r.field(owner, "DesignCache_Count", "integer")
    count = r.count("cache links")
    links = owner.add("DesignCache_Links", count)
    for _ in range(count):
        links.add("Link", r.argument('integer'))
    cache = owner.add("CacheLib")
    categories = cache.add("Categories")
    for _ in range(r.count("cache categories")):
        category = categories.add("Category", r.argument('text'), r.argument('integer'))
        for _ in range(r.count("cache category types")):
            kind = category.add("Type", r.argument('text'), r.argument('integer'))
            for _ in range(r.count("cache subtypes")):
                kind.add("Subtype", r.argument('text'), r.argument('integer'))
    folders = cache.add("Subfolders")
    for _ in range(r.count("cache subfolders")):
        folders.add("Folder", r.argument('text'))
    slots = cache.add("Slots")
    for index in range(r.count("cache slots")):
        slot = slots.add("Slot", index)
        for variant in range(r.count("cache slot variants")):
            inputs.append(read_definition(r, slot, variant, codecs))
    for slot in slots.children("Slot"):
        slot.set_values(slot.values[0], r.argument('text'))
    cache.annotations["incomplete"] = "later cache extensions and ASC projection remain"
    return tuple(inputs)


def write_definition(writer, definition, codecs):
    """Shared definition envelope with family-owned physical/symbol codecs."""
    part, pattern = definition.one('Part'), definition.one('Pattern')
    writer.field(part, 'Enabled', 'boolean')
    writer.field(part, 'PartType', 'integer')
    writer.field(part, 'PartName', 'text')
    writer.fields(part, 'integer', 'ShowNumbers Type Number1 Number2')
    writer.fields(part, 'number', 'Width Height')
    writer.fields(part, 'text', 'Name RefDes Value')
    writer.field(part, 'LockProperties', 'boolean')
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
