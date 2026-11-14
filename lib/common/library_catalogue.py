"""Identity-backed selections in standalone library catalogues.

Keys and labels are projections of a selected definition. Conflicting input
pairs remain explicit unresolved selections until the caller chooses a target.
Physical classifications in attached component footprints have a separate scope.
"""
from dataclasses import replace

from .library_metadata import CATEGORY_TYPE, CLASSIFICATIONS
from .reference_edits import assign_projected_reference, preview_references
from .references import Key, Property, ReferenceError
from .schema import Field


CATEGORY_ROLE = 'library-category'
TYPE_ROLE = 'library-category-type'
SUBTYPE_ROLE = 'library-category-subtype'
ROLES = (CATEGORY_ROLE, TYPE_ROLE, SUBTYPE_ROLE)
NAMES = dict(zip(ROLES, ('Category', 'TypeDefinition', 'SubTypeDefinition')))


def owner_of(source):
    while source is not None:
        if source.schema is not None and source.schema.fields.get('Category') is CATEGORY:
            return source
        source = source.parent
    return None


def _fields(source, role):
    if role == CATEGORY_ROLE:
        prefix = 'Pattern' if source.kind == 'Pattern' else 'Component'
        return prefix+'_CategoryIndex', prefix+'_CategoryName'
    return ('TypeIndex', 'Type') if role == TYPE_ROLE else ('SubTypeIndex', 'SubType')


def _pair(source, role):
    key, label = _fields(source, role)
    return source[key], source[label]


def _target(source, role, planned=None):
    if planned is not None and (source, role) in planned:
        return planned[source, role]
    links = source._owner().references.outgoing(source, role=role)
    if len(links) > 1:
        raise ReferenceError('catalogue selection has several targets')
    return links[0].target if links else None


def _scope(source, role, planned=None):
    owner = owner_of(source)
    if owner is None or (role == CATEGORY_ROLE and source is not owner) or (
            role != CATEGORY_ROLE and source.schema is not CLASSIFICATION):
        raise ReferenceError('catalogue selection must belong to a standalone library entry')
    root = owner._owner().one('/Library/Categories')
    if role == CATEGORY_ROLE:
        return root, 'Category'
    category = _target(owner, CATEGORY_ROLE, planned)
    if role == TYPE_ROLE:
        return (category, 'Type') if category is not None else (root, None)
    kind = _target(source, TYPE_ROLE, planned)
    return (kind, 'Subtype') if kind is not None else (category or root, None)


def projections(source, role):
    key, label = _fields(source, role)
    return (Key(source.one(key), name='Index'), Property(source.one(label), name='Name'))


def _selected(source, role):
    if source._owner() is None:
        return None
    target = _target(source, role)
    if target is not None:
        return target
    if _pair(source, role) != (-1, ''):
        raise ReferenceError('unavailable or conflicting catalogue selection; choose a definition explicitly')
    return None


def _validate_dependents(source, role):
    document = source._owner()
    if role == CATEGORY_ROLE:
        rows = source.one(('Pattern' if source.kind == 'Pattern' else 'Component')+'_CategoryTypes').children()
        roles = (TYPE_ROLE, SUBTYPE_ROLE)
    elif role == TYPE_ROLE:
        rows, roles = (source,), (SUBTYPE_ROLE,)
    else:
        return
    for row in rows:
        for dependent in roles:
            for reference in document.references.outgoing(row, role=dependent):
                validate_relationship(document, reference, reference.target)
            for issue in document.references._source_issues(row):
                if issue.message.startswith(dependent+':'):
                    validate_unresolved(issue)


def assign(source, target, role):
    document = source._owner()
    if document is None:
        raise ReferenceError('attach the entry before selecting a catalogue definition')
    if target is None:
        with preview_references(document.references,
                {link.uid: None for link in document.references.outgoing(source, role=role)}):
            _validate_dependents(source, role)
    key, label = _fields(source, role)
    assign_projected_reference(source, target, role=role, indices=projections(source, role),
                                clear_values={key: -1, label: ''})


def assign_scalar(source, value, role, *, key):
    """Named key/label assignment deliberately selects a matching definition."""
    document = source._owner()
    names = _fields(source, role)
    if document is None or not document._automatic_structure:
        source.set_field(names[0 if key else 1], value)
        return
    if value == (-1 if key else ''):
        assign(source, None, role)
        return
    scope, kind = _scope(source, role)
    matches = [node for node in scope.children(kind) if node['Index' if key else 'Name'] == value] if kind else []
    if len(matches) == 1:
        assign(source, matches[0], role)
        return
    values = {names[0]: value if key else -1, names[1]: '' if key else value}
    removals = {link.uid: None for link in document.references.outgoing(source, role=role)}
    with preview_references(document.references, removals):
        _validate_dependents(source, role)
    assign_projected_reference(source, None, role=role, clear_values=values)
    document.references.note(source, role+': unavailable or ambiguous explicit selection',
                              *projections(source, role), collections=(scope,))


def scalar_fields(fields, role):
    key, label = ('TypeIndex', 'Type') if role == TYPE_ROLE else ('SubTypeIndex', 'SubType')
    return {name: replace(fields[name], setter=lambda source, value, key=name == key:
                        assign_scalar(source, value, role, key=key)) for name in (key, label)}


def selection(name, role):
    return Field(name, 'reference', nullable=True,
        getter=lambda source: _selected(source, role),
        setter=lambda source, target: assign(source, target, role),
        reference_dependencies=lambda source: ((source, role, 'outgoing'),),
        value_dependencies=lambda source: tuple((source, name) for name in _fields(source, role)),
        description='Selected catalogue definition; its declared key and label stay coordinated.')


CATEGORY = selection('Category', CATEGORY_ROLE)
CLASSIFICATION = replace(CATEGORY_TYPE, name='LibraryClassification', fields={
    **CATEGORY_TYPE.fields,
    **scalar_fields(CATEGORY_TYPE.fields, TYPE_ROLE),
    **scalar_fields(CATEGORY_TYPE.fields, SUBTYPE_ROLE),
    'TypeDefinition': selection('TypeDefinition', TYPE_ROLE),
    'SubTypeDefinition': selection('SubTypeDefinition', SUBTYPE_ROLE),
})
CLASSIFICATION_ROWS = replace(CLASSIFICATIONS, name='LibraryClassifications', children={
    'CategoryType': replace(CLASSIFICATIONS.children['CategoryType'], record=CLASSIFICATION.name)})


def prepare_binding(reference):
    if reference.role not in ROLES:
        return reference
    expected = projections(reference.source, reference.role)
    if reference.indices and reference.indices != expected:
        raise ReferenceError('catalogue selections require their key and label projections')
    return replace(reference, indices=expected)


def validate_relationship(document, reference, target):
    scope, kind = _scope(reference.source, reference.role)
    if (kind is None or target.parent is not scope or target.kind != kind
            or target._owner() is not document):
        raise ReferenceError('catalogue target must belong to the selected parent definition')
    if any(link.uid != reference.uid for link in document.references.outgoing(reference.source, role=reference.role)):
        raise ReferenceError('catalogue selection already has a target')


def validate_change(document, reference, target):
    validate_relationship(document, reference, target)
    with preview_references(document.references, {reference.uid: replace(reference, target=target)}):
        _validate_dependents(reference.source, reference.role)


def validate_unresolved(issue):
    role = issue.message.partition(':')[0]
    scope, _ = _scope(issue.source, role)
    if _pair(issue.source, role) == (-1, '') or issue.collections != (scope,):
        raise ReferenceError('resolve or clear the unavailable catalogue choice before changing its scope')


def unresolved_fields(issue):
    role = issue.message.partition(':')[0]
    return ((issue.source, issue.source.schema.fields[NAMES[role]]),)


def plans(document, nodes, *, specifications=(), issues=()):
    """Discover unbound choices in parent-before-child order without mutation."""
    nodes = tuple(nodes)
    planned = {(source, role): target for source, target, role, _, _ in specifications if role in ROLES}
    claimed = set(planned)
    claimed.update((issue.source, issue.message.partition(':')[0]) for issue in issues)
    additions, unavailable = [], []
    owners = [node for node in nodes if node.schema is not None and node.schema.fields.get('Category') is CATEGORY]
    rows = [node for node in nodes if node.schema is CLASSIFICATION]
    for source, role in [*((owner, CATEGORY_ROLE) for owner in owners),
                         *((row, role) for row in rows for role in (TYPE_ROLE, SUBTYPE_ROLE))]:
        graph = document.references
        if ((source, role) in claimed or graph.outgoing(source, role=role)
                or any(issue.message.startswith(role+':') for issue in graph._source_issues(source))):
            continue
        pair = _pair(source, role)
        if pair == (-1, ''):
            continue
        scope, kind = _scope(source, role, planned)
        matches = [node for node in scope.children(kind) if (node['Index'], node['Name']) == pair] if kind else []
        indices = projections(source, role)
        if len(matches) == 1:
            planned[source, role] = matches[0]
            additions.append((source, matches[0], role, indices, ()))
        else:
            unavailable.append((source, role+': unavailable or conflicting key and label', indices, (scope,), ()))
    return additions, unavailable


def bind_imported(document):
    specifications, issues = plans(document, document.root._record_walk(include_self=True))
    for source, target, role, indices, guards in specifications:
        document.references.bind(source, target, *indices, role=role, guards=guards, preserve=True)
    for source, message, indices, collections, guards in issues:
        document.references.note(source, message, *indices, collections=collections, guards=guards)


def validate_complete(document):
    for source in document.root._record_walk(include_self=True):
        roles = (CATEGORY_ROLE,) if source.schema is not None and source.schema.fields.get('Category') is CATEGORY else (
            (TYPE_ROLE, SUBTYPE_ROLE) if source.schema is CLASSIFICATION else ())
        for role in roles:
            if _pair(source, role) != (-1, '') and not document.references.outgoing(source, role=role) and not any(
                    issue.message.startswith(role+':') for issue in document.references._source_issues(source)):
                raise ReferenceError('unbound catalogue selector; use relationship editing')


def check_resource_edit(document, record, name):
    if record.kind not in ('Category', 'Type', 'Subtype') or name not in ('Name', 'Index'):
        return
    for issue in document.references.issues:
        if issue.message.partition(':')[0] in ROLES:
            for scope in issue.collections or ():
                node = record
                while node is not None:
                    if node is scope:
                        raise ReferenceError('resolve unavailable catalogue selections before editing their scope')
                    node = node.parent
