"""Named field layouts and shared content traversal for the DCH adapter.

Layouts describe only the wire order and public document fields. Traversals
combine equivalent content from placed instances and cached definitions.
"""

COMPONENT_PLACEMENT = (
    ("Enabled", "boolean"), ("Selected", "boolean"),
    ("Type", "integer"), ("Number1", "integer"), ("Number2", "integer"),
    ("Page", "integer"), ("Orientation", "integer"), ("Group", "integer"), ("Number", "integer"),
    ("X", "number"), ("Y", "number"), ("Width", "number"), ("Height", "number"),
)

PIN_FONT = (("NameFontSize", "integer"), ("NameFontWidth", "number"), ("NameFontScale", "number"))


def placed_components(schematic):
    return schematic.child("Components").children("Part")


def cached_definitions(schematic):
    cache = schematic.child("CacheLib")
    if cache:
        for slot in cache.child("Slots").children("Slot"):
            yield from slot.children("Definition")


def symbols(schematic):
    yield from placed_components(schematic)
    for definition in cached_definitions(schematic):
        yield definition.child("Part")


def footprints(schematic):
    for part in placed_components(schematic):
        yield part.child("Pattern")
    for definition in cached_definitions(schematic):
        yield definition.child("Pattern")
    cache = schematic.child('CacheLib')
    if cache is not None:
        yield from cache.select('Patterns/Pattern')


def footprint_name(pattern):
    """A footprint owns one name string; an empty name is still valid text."""
    if len(pattern.arguments) != 1 or pattern.arguments[0].kind != 'string':
        raise ValueError(f'{pattern.path}: footprint requires one name string, which may be empty')
    return pattern.values[0]
