"""Active design-cache slot links, separate from unused serialized capacity."""
from .references import OrdinalGuard, Index
from .indexing import at, integer


def specifications(owner, *, scope=None):
    count = owner.child('DesignCache_Count')
    if scope is not None and not (scope.select(owner, 'CacheLib/Slots/Slot') or
            scope.select(owner, 'DesignCache_Links/Link') or count in scope.nodes):
        return
    cache = owner.child('CacheLib')
    slots = cache.child('Slots') if cache is not None else None
    if slots is None:
        return
    records = slots._child_sequence('Slot')
    selected_slots = scope.select(cache, 'Slots/Slot') if scope is not None else cache.select('Slots/Slot')
    for slot in selected_slots:
        index = slot.schema.fields.get('Index') if slot.schema is not None else None
        if slot.arguments and (index is None or index.getter is None):
            yield slot, slot, 'cache-slot-order', (Index(slot),), ()
    links = owner.child('DesignCache_Links')
    active = integer(count.values[0]) if count is not None and count.arguments else None
    if active is None or links is None:
        return
    # Count is a last-active index. Later capacity records remain literal facts;
    # they must not acquire the meaning of live references during a slot move.
    selected = links.children('Link') if scope is None or count in scope.nodes else scope.select(owner, 'DesignCache_Links/Link')
    for link in selected:
        if link._ordinal() > active:
            continue
        if link.arguments:
            yield owner, at(records, link.values[0]), 'design-cache-slot', (Index(link),), (OrdinalGuard(count, link),)


def issue_collections(source, role):
    if role == 'design-cache-slot':
        cache = source.child('CacheLib')
        slots = cache.child('Slots') if cache is not None else None
        return (slots,) if slots is not None else None
    return None
