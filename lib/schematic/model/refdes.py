"""Component RefDes occupancy checks over current, named model values."""
from ...common.refdes import split_refdes


def components(document):
    """Enabled physical components across every sheet, excluding cache entries."""
    schematic = document.root.child('Schematic')
    collection = schematic.child('Components') if schematic is not None else None
    return (part for part in collection._child_sequence('Part')
            if part['Enabled'] and part['PartType'] == 0) if collection is not None else iter(())


def _key(name):
    try:
        return split_refdes(name)
    except ValueError:
        return None


def _stored_name(part):
    values = part.child('RefDes')._stored_arguments()
    return values[0].value if values else ''


def validate_name(document, part, *, previous=None, parent=None):
    """Prevent new occupancy collisions, retaining existing multipart names.

    Equal literal names can describe units of one multipart component. Joining
    different occupied names is a coordinated operation, beyond an individual
    field assignment. A spelling-only change is valid for an unshared name.
    """
    parent = part.parent if parent is None else parent
    if (part.kind != 'Part' or parent is not document.one('/Schematic/Components')
            or not part['Enabled'] or part['PartType'] != 0):
        return
    name = part['RefDes']
    key = split_refdes(name) if name else None
    if key is None or name == previous:
        return
    for other in components(document):
        if other is part or _key(other['RefDes']) != key:
            continue
        if other['RefDes'] == name and (previous is None or _key(_stored_name(other)) == _key(previous)):
            # New multipart records may share a literal name. Existing units
            # may also follow a managed, coordinated change of their own group.
            continue
        raise ValueError(f"RefDes {name!r} is already occupied by {other['RefDes']!r}")


def validate_edit(document, record, name):
    if record.kind != 'Part' or name not in ('RefDes', 'Enabled', 'PartType'):
        return
    previous = _stored_name(record) if name == 'RefDes' else None
    validate_name(document, record, previous=previous)
