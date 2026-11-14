"""Scoped reference rules for shared unplaced footprint definitions."""
from .dimension_refs import matches_local_attachment
from .references import ReferenceError
from . import unplaced_footprint_records as records


ROLES = (records.GROUP_ROLE, records.PAD_ROLE, *records.DIMENSION_ROLES, *records.CONNECTION_ROLES)

_SELECTIONS = ((records.GROUP_ROLE, 'Group', 'GroupId'),
               (records.PAD_ROLE, 'Pad', 'PadId'),
               *zip(records.CONNECTION_ROLES, ('Pad1', 'Pad2'), ('X', 'Y')))


def pattern_of(node):
    while node is not None:
        if node.kind == 'Pattern':
            return node
        node = node.parent
    return None


def validate_relationship(document, reference, target):
    owner = pattern_of(reference.source)
    if reference.role == records.GROUP_ROLE:
        field = reference.source.schema.fields.get('Group') if reference.source.schema else None
        valid = (field is not None and field.kind == 'reference'
                 and owner is not None and target.schema is records.GROUP
                 and target.parent is owner.child('Pattern_Groups') and target['Enabled'])
    elif reference.role == records.PAD_ROLE:
        valid = (owner is not None and reference.source.schema is records.DRAWING
                 and target.schema is records.PAD and target.parent is owner.child('Pads'))
    elif reference.role in records.CONNECTION_ROLES:
        valid = (owner is not None and reference.source.schema is records.PAIR
                 and reference.source.parent is owner.child('InternalConnections')
                 and target.schema is records.PAD and target.parent is owner.child('Pads'))
    elif reference.role in records.DIMENSION_ROLES:
        source, side = reference.source, reference.role[-1]
        valid = (source.schema is records.DIMENSION and owner is not None and source['Enabled']
                 and source.parent is owner.child('Dimensions')
                 and matches_local_attachment(owner, source['Connected'+side], source['Point'+side], target))
    else:
        raise ReferenceError(f'unknown footprint relationship role: {reference.role}')
    if not valid or target._owner() is not document:
        raise ReferenceError('relationship target must belong to the same pattern')
    if any(link.uid != reference.uid for link in document.references.outgoing(reference.source, role=reference.role)):
        raise ReferenceError('relationship already has a target')


def unresolved_fields(issue):
    for role, name, _ in _SELECTIONS:
        if issue.message.startswith(role+':'):
            return ((issue.source, issue.source.schema.fields[name]),)
    return ()


def validate_unresolved(issue):
    owner = pattern_of(issue.source)
    if owner is None or any(pattern_of(scope) is not owner for scope in issue.collections):
        raise ReferenceError('resolve or clear an unavailable selection before changing its pattern scope')
    for role, _, index in _SELECTIONS:
        if issue.message.startswith(role+':') and issue.source.child('Unresolved'+index) is None:
            raise ReferenceError('unavailable selection requires its explicit model key')
