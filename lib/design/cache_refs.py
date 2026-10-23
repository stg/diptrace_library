"""Active design-cache slot links, separate from unused serialized capacity."""
from .references import Guard, Index
from .schematic_refs import _at, _integer


def specifications(document):
    if document.representation != 'schematic':
        return
    schematic = document.one('/Schematic')
    cache = schematic.child('CacheLib')
    slots = cache.child('Slots') if cache is not None else None
    if slots is None:
        return
    records = slots.children('Slot')
    for slot in records:
        if slot.arguments:
            yield slot, slot, 'cache-slot-order', (Index(slot),), ()
    count = schematic.child('DesignCache_Count')
    links = schematic.child('DesignCache_Links')
    active = _integer(count.values[0]) if count is not None and count.arguments else None
    if active is None or links is None:
        return
    # Count is a last-active index. Later capacity records remain literal facts;
    # they must not acquire the meaning of live references during a slot move.
    for link in links.children('Link')[:max(0, active+1)]:
        if link.arguments:
            yield schematic, _at(records, _integer(link.values[0])), 'design-cache-slot', (Index(link),), (Guard(count, count.values),)


def issue_collections(source, role):
    if role == 'design-cache-slot':
        cache = source.child('CacheLib')
        slots = cache.child('Slots') if cache is not None else None
        return (slots,) if slots is not None else None
    return None
