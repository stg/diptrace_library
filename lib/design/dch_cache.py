"""DCH project libraries and cached definitions, directly into our model."""
from .model import Element, SourceSpan
from .dch_records import PIN_FONT
from .dch import (_component_shapes, _pattern_graphics, _pattern_model,
                  _pattern_pads, _pattern_parameters)


def _types(r, parent, kind):
    count = r.count(kind)
    node = parent.add(kind, count)
    for _ in range(count):
        node.add("Type", r.argument('text'), r.argument('text'), r.argument('integer'), r.argument('integer'))


def _user_fields(r, parent, *, symbol=False):
    fields = parent.add("UserFields")
    for _ in range(r.count("cached user fields")):
        node = fields.add("UserField", r.argument('text'), r.argument('text'), r.argument('integer'))
        if symbol:
            # Cached symbol label choices are zero-initialized and absent from
            # the DCH wire, but format cl_UserField emits their seven values.
            node.set_values(*node.arguments, *(0 for _ in range(7)))
            node.annotations['label_defaults_for_version'] = r.header.version


def _discard_groups(r, member_kinds):
    """Consume obsolete member lists; current groups have their own extension."""
    for _ in range(r.count("obsolete cached groups")):
        r.boolean()
        r.integer()
        for _ in member_kinds:
            for _ in range(r.count("group members")):
                r.integer()


def _symbol_pins(r, part):
    pins = part.add("Pins")
    for index in range(r.count("cached symbol pins")):
        start = r.pos
        pin = pins.add("Pin", index)
        r.field(pin, "Enabled", "boolean")
        for name in ("Type", "Orientation", "Number"):
            r.field(pin, name, "integer")
        pin.set_values(index, r.argument('number'), r.argument('number'))
        r.field(pin, "Length", "number")
        for name in ("Name", "StringNumber"):
            r.field(pin, name, "text")
        # Cached symbol pins have no placed-net connection state. The boolean
        # here is ShowName (format pin member +3), unlike placed FConnect (+2).
        r.field(pin, "ShowName", "boolean")
        for name in ("PinNumXShift", "PinNumYShift", "PinNameXShift", "PinNameYShift"):
            r.field(pin, name, "number")
        r.field(pin, "ElectricType", "integer")
        
        # placed pins this cache wire has Locked, with no Hidden occurrence.
        r.field(pin, "Locked", "boolean")
        r.field(pin, "ModelSig", "text")
        r.fields(pin, PIN_FONT)
        pin.source = SourceSpan("dch", start, r.pos, r.source)


def _definition(r, slot, variant):
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
    _pattern_parameters(r, pattern)
    for name in ("Origin_X", "Origin_Y"):
        r.field(part, name, "number")
    points = pattern.add("PadPoints")
    for _ in range(r.count("cached default pad points")):
        points.add("pt", r.argument('number'), r.argument('number'))
    pattern.annotations["declared_pad_count"] = r.count("cached pads")
    # Cache ASC emits the reserved records as well (unlike placed footprints).
    _pattern_pads(r, pattern, omit_reserved=False)
    _pattern_graphics(r, pattern)
    _discard_groups(r, ("Pads", "Shapes", "Holes"))
    _user_fields(r, pattern)
    _pattern_model(r, pattern)
    r.field(pattern.child('Model3D'), 'Units', 'integer')
    r.field(pattern, "Mounting", "integer")
    r.field(pattern, "Pattern_CategoryName", "text")
    r.field(pattern, "Pattern_CategoryIndex", "integer")
    _types(r, pattern, "Pattern_CategoryTypes")
    count = r.count("cached possible names")
    names = pattern.add("PossibleNames", count)
    for _ in range(count):
        names.add("PossibleName", r.argument('text'))
    _symbol_pins(r, part)
    part.annotations["declared_shape_count"] = r.count("cached symbol shapes")
    _component_shapes(r, part, placed=False)
    _discard_groups(r, ("Pins", "Shapes"))
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
    r.field(part, 'ModelNote', 'text')
    r.field(part, "Manufacturer", "text")
    r.field(part, "Component_CategoryName", "text")
    r.field(part, "Component_CategoryIndex", "integer")
    _types(r, part, "Component_CategoryTypes")
    definition.source = SourceSpan("dch", start, r.pos, r.source)
    part.annotations["incomplete"] = "later cached-symbol extensions and ASC projection remain"
    definition.annotations["incomplete"] = "later cache extensions and ASC projection remain"
    return definition


def read_cache(r, schematic):
    for kind, name in [("text", "ProjectLibs_Name"), ("integer", "ProjectLibs_Type"),
                       ("integer", "ProjectLibs_Content")]:
        r.field(schematic, name, kind)
    for name, child in (("ProjectLibs_Folders", "Folder"), ("ProjectLibs_Libs", "Lib")):
        count = r.count(name)
        paths = schematic.add(name, count)
        for _ in range(count):
            paths.add(child, r.argument('text'))
    r.field(schematic, "ProjectLibs_Sorted", "boolean")
    r.field(schematic, "DesignCache_Count", "integer")
    count = r.count("cache links")
    links = schematic.add("DesignCache_Links", count)
    for _ in range(count):
        links.add("Link", r.argument('integer'))
    cache = schematic.add("CacheLib")
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
            _definition(r, slot, variant)
    for slot in slots.children("Slot"):
        slot.set_values(slot.values[0], r.argument('text'))
    cache.annotations["incomplete"] = "later cache extensions and ASC projection remain"
