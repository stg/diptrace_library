"""Group membership and local title-field identities in shared schematics."""
from ...common.references import (Index)
from .local_keys import (missing_key)
from .refs import (_at, _integer, _children)
from .reference_scope import select as source_records, OrdinalLookup


def specifications(document, *, scope=None):
    from .definitions import has_derived_index
    schematic = document.root.child('Schematic')
    if schematic is None:
        return
    active = schematic.child('ActiveSheet')
    if active is not None:
        yield active, _at(_children(schematic, 'Pages', 'Page'), _integer(active.values[0])), 'active-sheet', (Index(active),), ()
    groups = _children(schematic, 'Groups', 'Group')
    keys = {}
    for group in source_records(schematic, 'Groups/Group', scope):
        key = group.values[0]
        keys[key] = group if key not in keys else None
        yield group, group, 'group-order', (Index(group),), ()
    if scope is not None:
        keys = OrdinalLookup(groups)
    owners = []
    for path in ('Components/Part', 'Shapes/Shape', 'Tables/Table', 'PageConnectors/PageConnector',
                 'Nets/Net/Lines/Line', 'Buses/Bus/Lines/Line'):
        owners.extend(source_records(schematic, path, scope))
    for owner in owners:
        group = owner.child('Group')
        if group is not None and group.values[0] >= 0:
            yield owner, keys.get(group.values[0]), 'schematic-group', (Index(group),), ()
    for grid in source_records(schematic, 'Pages/Page/TitleBlocks/TitleBlock', scope):
        contents = _children(grid, 'Contents', 'Content')
        for item in source_records(grid, 'Contents/Content', scope):
            if not has_derived_index(item):
                yield item, item, 'title-field-order', (Index(item),), ()
        for cell in source_records(grid, 'Cells/Cell', scope):
            if len(cell.arguments) == 3 and cell.values[2] >= 0:
                index = cell.values[2]
                target = _at(contents, index)
                yield cell, target, 'title-cell-field', (Index(cell, argument=2),), ()
    nets = {}
    if scope is not None:
        nets = OrdinalLookup(_children(schematic, 'Nets', 'Net'))
    else:
        for net in schematic.select('Nets/Net'):
            key = net.scalar('Number')
            nets[key] = net if key not in nets else None
    classes = _children(schematic, 'NetClasses', 'NetClass')
    for pair in source_records(schematic, 'DifferentialPairs/DifferentialPair', scope):
        if len(pair.arguments) != 7:
            continue
        for argument, role in ((2, 'differential-positive'), (3, 'differential-negative'),
                               (4, 'differential-class')):
            key = pair.values[argument]
            if key >= 0:
                target = _at(classes, key) if argument == 4 else nets.get(key)
                yield pair, target, role, (Index(pair, argument=argument),), ()
    if document.representation != 'schematic':
        return
    from .traversal import (footprints, cached_definitions, symbols)
    for part in symbols(schematic, scope=scope):
        shapes = source_records(part, 'Shapes/Shape', scope)
        if not shapes:
            continue
        users = _children(part, 'UserFields', 'UserField')
        for shape in shapes:
            field = shape.child('FontType')
            kind = _integer(field.values[0]) if field is not None and len(field.arguments) == 1 else None
            if kind is not None and kind >= 20:
                yield shape, _at(users, kind-20), 'marking-user-field', (Index(field, offset=20),), ()
    for pattern in footprints(schematic, scope=scope):
        if pattern is None:
            continue
        groups = _children(pattern, 'Pattern_Groups', 'pt')
        for path in ('Pads/Pad', 'Shapes/Shape', 'Dimensions/Dimension'):
            records = source_records(pattern, path, scope)
            if path != 'Dimensions/Dimension':
                records = records[1:-1] if scope is None else [record for record in records
                    if 0 < record._ordinal() < len(record.parent.children(record.kind))-1]
            for item in records:
                field = item.child('Group')
                missing = missing_key(item, 'Group')
                if missing is not None:
                    yield item, None, 'pattern-group', (Index(missing, argument=1), Index(field)), ()
                elif field is not None and field.values[0] >= 0:
                    key = field.values[0]
                    target = _at(groups, key)
                    yield item, target, 'pattern-group', (Index(field),), ()
        holes = _children(pattern, 'Holes', 'Hole')
        for hole in source_records(pattern, 'Holes/Hole', scope):
            if not 0 < hole._ordinal() < len(holes)-1:
                continue
            missing = missing_key(hole, 'Group')
            if missing is not None:
                yield hole, None, 'pattern-group', (Index(missing, argument=1), Index(hole, argument=6)), ()
            elif len(hole.arguments) == 7 and hole.values[6] >= 0:
                key = hole.values[6]
                target = _at(groups, key)
                yield hole, target, 'pattern-group', (Index(hole, argument=6),), ()
    for definition in cached_definitions(schematic, scope=scope):
        part = definition.one('Part') if scope is None else definition.child('Part')
        if part is None:
            continue
        groups = _children(part, 'Groups', 'pt')
        for path in ('Pins/Pin', 'Shapes/Shape'):
            for item in source_records(part, path, scope):
                field = item.child('Group')
                missing = missing_key(item, 'Group')
                if missing is not None:
                    yield item, None, 'symbol-group', (Index(missing, argument=1), Index(field)), ()
                elif field is not None and field.values[0] >= 0:
                    key = field.values[0]
                    target = _at(groups, key)
                    yield item, target, 'symbol-group', (Index(field),), ()


def local_collection(source, role):
    if role == 'active-sheet':
        return source.parent.child('Pages')
    if role == 'marking-user-field':
        return source.parent.parent.child('UserFields')
    if role == 'schematic-group':
        owner = source
        while owner is not None and owner.kind != 'Schematic':
            owner = owner.parent
        return owner.child('Groups') if owner is not None else None
    if role == 'title-cell-field':
        return source.parent.parent.child('Contents')
    if role.startswith('differential-'):
        return source.parent.parent.child('NetClasses' if role == 'differential-class' else 'Nets')
    if role in ('pattern-group', 'symbol-group'):
        return source.parent.parent.child('Pattern_Groups' if role == 'pattern-group' else 'Groups')
    return None


def issue_collections(source, role):
    owner = local_collection(source, role)
    return (owner,) if owner is not None else None
