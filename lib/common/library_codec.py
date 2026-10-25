"""Shared project-library settings, catalogues and embedded definitions."""
from dataclasses import dataclass
from typing import Callable

from .model import Element, SourceSpan
from .catalog_codec import read_category_types, read_possible_names
from .symbol_codec import read_cached_pins


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
