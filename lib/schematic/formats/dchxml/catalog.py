"""Schematic XML category coverage for binary conversion diagnostics."""


def unrepresented_pattern_categories(schematic):
    """Catalog labels which embedded DCH footprint records cannot carry."""
    cache = schematic.child('CacheLib')
    categories = cache.child('PatternCategories') if cache is not None else None
    if categories is None:
        return set()
    facts = set()
    for category in categories.children('Category'):
        name = category.values[0]
        facts.add((name, '', ''))
        for kind in category.children('Type'):
            label = kind.values[0]
            facts.add((name, label, ''))
            for subtype in kind.children('Subtype'):
                facts.add((name, label, subtype.values[0]))
    from ...model.traversal import (footprints)
    covered = set()
    for pattern in footprints(schematic):
        name = pattern.scalar('Pattern_CategoryName', '')
        if name:
            covered.add((name, '', ''))
        for row in pattern.select('Pattern_CategoryTypes/CategoryType'):
            kind, subtype = row.values[:2]
            if kind:
                covered.add((name, kind, ''))
            if subtype:
                covered.add((name, kind, subtype))
    return facts-covered
