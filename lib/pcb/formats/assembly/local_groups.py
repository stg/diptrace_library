"""Consume cached local-group positions into current identity links."""
from ....common.conversion import import_notice
from ...model.local_groups import PATTERN_GROUP, SYMBOL_GROUP
from ...model.library_records import patterns
from ..errors import PcbError


def _key(source):
    field = source.child('Group')
    if field is not None:
        return field.values[0]
    if source.kind == 'Hole' and len(source.arguments) > 6:
        return source.values[6]
    return -1


def _public_missing(source):
    container = source.child('UnresolvedKeys')
    if container is None:
        return None
    rows = container.children()
    if (container.arguments or len(rows) != 1 or rows[0].kind != 'Key'
            or rows[0].values[:1] != ('Group',) or len(rows[0].values) != 2
            or type(rows[0].values[1]) is not int or rows[0].values[1] < 0):
        raise PcbError('unresolved local keys need a supported field and integer selector')
    value = rows[0].values[1]
    container.detach()
    return value


def prepare_local_groups(board):
    links, inactive, cleared, missing = [], [], [], []
    for owners, collection, paths, role in (
            (patterns(board), 'Pattern_Groups', ('Pads/Pad', 'Shapes/Shape', 'Holes/Hole', 'Dimensions/Dimension'), PATTERN_GROUP),
            (board.select('CacheLib/Slots/Slot/Definition/Part'), 'Groups', ('Pins/Pin', 'Shapes/Shape'), SYMBOL_GROUP)):
        for owner in owners:
            groups = owner.child(collection)
            if groups is None:
                groups = owner.add(collection)
            rows = groups.children('pt') if groups is not None else ()
            compacted = any(not group.values[0] for group in rows)
            targets = {}
            for index, group in enumerate(rows):
                if group.values[0]:
                    targets[index] = group
                else:
                    inactive.append(group)
            for path in paths:
                for source in owner.select(path):
                    public = _public_missing(source)
                    key = _key(source) if public is None else public
                    target = targets.get(key) if public is None else None
                    if target is not None:
                        links.append((source, role, target))
                    elif key >= 0:
                        if compacted and public is None:
                            cleared.append(source)
                        else:
                            field = source.add('UnresolvedGroupId', key)
                            missing.append((source, role, field, groups))
                    if (field := source.child('Group')) is not None:
                        field.detach()
                    if source.kind == 'Hole' and len(source.arguments) > 6:
                        source.set_values(*source.arguments[:6])
    if inactive or cleared:
        import_notice('info', 'local-group-normalization',
            f'Removed {len(inactive)} inactive local groups and cleared {len(cleared)} unavailable group assignments.',
            cleared, recoverability='current local group identities retained')
    for group in inactive:
        group.detach()
    return links, missing
