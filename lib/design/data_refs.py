"""Group membership and local title-field identities in shared schematics."""
from .references import Index
from .local_keys import missing_key
from .schematic_refs import _at, _integer


def specifications(document):
    schematic = document.root.child('Schematic')
    if schematic is None:
        return
    groups = schematic.select('Groups/Group')
    keys = {}
    for group in groups:
        key = group.values[0]
        keys[key] = group if key not in keys else None
        yield group, group, 'group-order', (Index(group),), ()
    owners = []
    for path in ('Components/Part', 'Shapes/Shape', 'Tables/Table', 'PageConnectors/PageConnector',
                 'Nets/Net/Lines/Line', 'Buses/Bus/Lines/Line'):
        owners.extend(schematic.select(path))
    for owner in owners:
        group = owner.child('Group')
        if group is not None and group.values[0] >= 0:
            yield owner, keys.get(group.values[0]), 'schematic-group', (Index(group),), ()
    for grid in schematic.select('Pages/Page/TitleBlocks/TitleBlock'):
        contents = grid.select('Contents/Content')
        for item in contents:
            yield item, item, 'title-field-order', (Index(item),), ()
        for cell in grid.select('Cells/Cell'):
            if len(cell.arguments) == 3 and cell.values[2] >= 0:
                index = cell.values[2]
                target = _at(contents, index)
                yield cell, target, 'title-cell-field', (Index(cell, argument=2),), ()
    nets = {}
    for net in schematic.select('Nets/Net'):
        key = net.scalar('Number')
        nets[key] = net if key not in nets else None
    classes = schematic.select('NetClasses/NetClass')
    for pair in schematic.select('DifferentialPairs/DifferentialPair'):
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
    from .dch_records import footprints, cached_definitions, symbols
    for part in symbols(schematic):
        users = part.select('UserFields/UserField')
        for shape in part.select('Shapes/Shape'):
            field = shape.child('FontType')
            kind = _integer(field.values[0]) if field is not None and len(field.arguments) == 1 else None
            if kind is not None and kind >= 20:
                yield shape, _at(users, kind-20), 'marking-user-field', (Index(field, offset=20),), ()
    for pattern in footprints(schematic):
        if pattern is None:
            continue
        groups = pattern.select('Pattern_Groups/pt')
        for path in ('Pads/Pad', 'Shapes/Shape', 'Dimensions/Dimension'):
            records = pattern.select(path)
            if path != 'Dimensions/Dimension':
                records = records[1:-1]
            for item in records:
                field = item.child('Group')
                missing = missing_key(item, 'Group')
                if missing is not None:
                    yield item, None, 'pattern-group', (Index(missing, argument=1), Index(field)), ()
                elif field is not None and field.values[0] >= 0:
                    key = field.values[0]
                    target = _at(groups, key)
                    yield item, target, 'pattern-group', (Index(field),), ()
        for hole in pattern.select('Holes/Hole')[1:-1]:
            missing = missing_key(hole, 'Group')
            if missing is not None:
                yield hole, None, 'pattern-group', (Index(missing, argument=1), Index(hole, argument=6)), ()
            elif len(hole.arguments) == 7 and hole.values[6] >= 0:
                key = hole.values[6]
                target = _at(groups, key)
                yield hole, target, 'pattern-group', (Index(hole, argument=6),), ()
    for definition in cached_definitions(schematic):
        part = definition.one('Part')
        groups = part.select('Groups/pt')
        for path in ('Pins/Pin', 'Shapes/Shape'):
            for item in part.select(path):
                field = item.child('Group')
                missing = missing_key(item, 'Group')
                if missing is not None:
                    yield item, None, 'symbol-group', (Index(missing, argument=1), Index(field)), ()
                elif field is not None and field.values[0] >= 0:
                    key = field.values[0]
                    target = _at(groups, key)
                    yield item, target, 'symbol-group', (Index(field),), ()


def local_collection(source, role):
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
