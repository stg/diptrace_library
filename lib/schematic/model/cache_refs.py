"""Active design-cache slot links, separate from unused serialized capacity."""
from ...common.references import (OrdinalGuard, Index)
from .refs import (_at, _integer)
from .reference_scope import select as source_records


def specifications(document, *, scope=None):
    if document.representation != 'schematic':
        return
    schematic = document.one('/Schematic')
    count = schematic.child('DesignCache_Count')
    if scope is not None and not (scope.select(schematic, 'CacheLib/Slots/Slot') or
            scope.select(schematic, 'DesignCache_Links/Link') or count in scope.nodes):
        return
    cache = schematic.child('CacheLib')
    slots = cache.child('Slots') if cache is not None else None
    if slots is None:
        return
    records = slots._child_sequence('Slot')
    from .definitions import has_derived_index
    for slot in source_records(cache, 'Slots/Slot', scope):
        if slot.arguments and not has_derived_index(slot):
            yield slot, slot, 'cache-slot-order', (Index(slot),), ()
    links = schematic.child('DesignCache_Links')
    active = _integer(count.values[0]) if count is not None and count.arguments else None
    if active is None or links is None:
        return
    # Count is a last-active index. Later capacity records remain literal facts;
    # they must not acquire the meaning of live references during a slot move.
    selected = links.children('Link') if scope is None or count in scope.nodes else scope.select(schematic, 'DesignCache_Links/Link')
    for link in selected:
        if link._ordinal() > active:
            continue
        if link.arguments:
            yield schematic, _at(records, _integer(link.values[0])), 'design-cache-slot', (Index(link),), (OrdinalGuard(count, link),)


def issue_collections(source, role):
    if role == 'design-cache-slot':
        cache = source.child('CacheLib')
        slots = cache.child('Slots') if cache is not None else None
        return (slots,) if slots is not None else None
    return None
