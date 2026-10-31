"""Consume supplied classification validity and labels into current groups."""
from ....common.conversion import import_notice
from ...model import pour_regions


def prepare(upgrades):
    links, unavailable = [], []
    for upgrade in upgrades:
        pour = upgrade.pour
        if not pour.get('Enabled', True) or (fill := pour.child('Fill')) is None:
            continue
        members = []
        for primitive in pour_regions.primitives(fill):
            field = primitive.child('Region')
            label = field.values[0] if field is not None else -1
            if field is not None:
                field.detach()
            members.append((primitive, label))
        if upgrade.regions_counted:
            collection = fill.add('Regions')
            groups = {label: collection.add('Region', label)
                      for label in sorted({label for _, label in members if label >= 0})}
            links.extend((primitive, group) for primitive, label in members
                         if (group := groups.get(label)) is not None)
        elif members:
            unavailable.append(pour)
    if unavailable:
        import_notice('info', 'pour-regions-unavailable',
            'Unavailable calculated pour classification does not retain stale group labels.', unavailable,
            recoverability='fill geometry and settings remain; a geometric editor can classify the supplied fill')
    return links
