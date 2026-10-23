"""Unresolved public references are current facts, distinct from assignments."""


_FIELDS = dict(Pin=('Group', 'PadId'), Pad=('Group',), Shape=('Group', 'PadId'),
               Hole=('Group',), Dimension=('Group', 'SubObject1', 'SubObject2'), IntCon=('X', 'Y'))


def _rows(owner):
    containers = owner.children('UnresolvedKeys')
    if not containers:
        return ()
    if len(containers) != 1 or containers[0].arguments:
        raise ValueError(f'{owner.path}: expected one unresolved-key collection without arguments')
    rows, names = containers[0].children(), set()
    for row in rows:
        if row.kind != 'Key' or row.children():
            raise ValueError(f'{row.path}: unsupported unresolved-reference record')
        if (len(row.arguments) != 2 or row.arguments[0].kind != 'string'
                or row.arguments[1].kind != 'number' or row.arguments[1].unit
                or row.values[1] < 0 or int(row.values[1]) != row.values[1]):
            raise ValueError(f'{row.path}: an unresolved key needs a field name and nonnegative integer')
        name = row.values[0]
        if name not in _FIELDS.get(owner.kind, ()):
            raise ValueError(f'{row.path}: unsupported unresolved-reference field {name}')
        if name in names:
            raise ValueError(f'{owner.path}: duplicate unresolved key {name}')
        names.add(name)
    return rows


def validate_keys(document):
    for owner in document.root.walk(include_self=True):
        _rows(owner)


def missing_key(owner, name):
    return next((row for row in _rows(owner) if row.values[0] == name), None)


def map_key(owner, name, key, mapping):
    if key < 0 or key in mapping:
        return mapping.get(key, key)
    keys = owner.child('UnresolvedKeys') or owner.add('UnresolvedKeys')
    keys.add('Key', name, key)
    return -1


def copy_missing_keys(source, target):
    _rows(source)
    keys = source.child('UnresolvedKeys')
    if keys is not None:
        target.append(keys.clone())


def project_key(owner, name, value, mapping=None):
    missing = missing_key(owner, name)
    if missing is not None:
        return missing.values[1]
    return mapping.get(value, value) if mapping is not None else value


def public_keys(records, reserved=(), *, start=0):
    """Assign stable-in-order keys without giving an unresolved key a target."""
    used = set(reserved)
    result = {}
    for index, _ in enumerate(records, start):
        key = index
        while key in used:
            key += 1
        result[index] = key
        used.add(key)
    return result


def reserved_keys(owners, names):
    return {row.values[1] for owner in owners for name in names
            if (row := missing_key(owner, name)) is not None}


def prepare_positional_keys(document, *, destination, report=None):
    """Detach only absent public targets in a positional destination view."""
    from .conversion import warn
    missing = []
    for owner in document.root.walk(include_self=True):
        for row in _rows(owner):
            name = row.values[0]
            missing_key(owner, name)  # Validate typed data before changing output.
            if name in ('SubObject1', 'SubObject2'):
                owner.set_field('Connected'+name[-1], -1)
            missing.append(row)
    if missing:
        pads = [row for row in missing if row.parent.parent.kind == 'Pin' and row.values[0] == 'PadId']
        others = [row for row in missing if row not in pads]
        for rows, rule in ((pads, 'unresolved-pad-assignment'), (others, 'unresolved-local-reference')):
            if rows:
                warn(report, rule, destination,
                     'public keys without a positional target export as unassigned', rows,
                     recoverability='the unresolved keys remain in the authoring model')
        fields = set(missing)
        for issue in list(document.references.issues):
            if any(index.field in fields for index in issue.indices):
                document.references.discard_issue(issue)
        containers = {row.parent for row in missing}
        for row in missing:
            row.detach()
        for container in containers:
            container.detach()
