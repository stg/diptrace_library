"""Shared schematic content traversal."""


def placed_components(schematic):
    return schematic.child("Components").children("Part")


def cached_definitions(schematic, *, scope=None):
    if scope is not None:
        yield from scope.select(schematic, 'CacheLib/Slots/Slot/Definition')
        return
    cache = schematic.child("CacheLib")
    if cache:
        for slot in cache.child("Slots").children("Slot"):
            yield from slot.children("Definition")


def symbols(schematic, *, scope=None):
    yield from scope.select(schematic, 'Components/Part') if scope is not None else placed_components(schematic)
    for definition in cached_definitions(schematic, scope=scope):
        part = definition.child('Part')
        if part is not None:
            yield part


def footprints(schematic, *, scope=None):
    if scope is not None:
        for path in ('Components/Part/Pattern', 'CacheLib/Slots/Slot/Definition/Pattern', 'CacheLib/Patterns/Pattern'):
            yield from scope.select(schematic, path)
        return
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
