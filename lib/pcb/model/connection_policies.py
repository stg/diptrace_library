"""One connection policy per selected pad group, with derived membership.

Pad selects the group to which the policy applies. It is an identity reference,
so the setting follows that pad through reordering. Changing connectivity can
require removing or retargeting an affected policy before merging groups.
"""
from dataclasses import replace

from ...common.reference_edits import preview_references
from ...common.references import ReferenceError
from ...common.schema import Child, Field, Record
from . import internal_connections
from .connection_groups import groups, ratlines
from .membership import component_of
from .relationships import linked, reference_field


ROLE = 'internal-group-policy'


def owner(policy):
    collection = policy.parent
    component = collection.parent if collection is not None else None
    return component if (collection is not None and collection.kind == 'InternalConnections'
                         and component is not None and component.kind == 'Component') else None


def members(policy):
    component, pad = owner(policy), linked(policy, ROLE)
    if component is None or pad is None:
        return None
    return next((group for group in groups(component, strict=False) if pad in group), None)


def display_tree(policy):
    selected = members(policy)
    return ratlines(selected) if selected is not None else None


def group_number(pad):
    component = component_of(pad)
    return next((index for index, group in enumerate(groups(component, strict=False)) if pad in group), -1) if component else -1


def _component(record):
    return component_of(record) if record.kind == 'Pad' else owner(record)


def values(record):
    component = _component(record)
    return tuple((pad, name) for pad in component.select('Pattern/Pads/Pad')
                 for name in ('StringNumber', 'PadShape_New')) if component is not None else ()


def references(record):
    component = _component(record)
    result = tuple((pair, role, 'outgoing') for pair in component.select('IntConRecords/Item')
                   for role in internal_connections.ROLES) if component is not None else ()
    return result + (((record, ROLE, 'outgoing'),) if record.kind == 'IntCon' else ())


def collections(record):
    component = _component(record)
    if component is None:
        return ()
    result = [(component.one('Pattern/Pads'), 'Pad'), (component, 'IntConRecords')]
    if (definitions := component.child('IntConRecords')) is not None:
        result.append((definitions, 'Item'))
    return tuple(result)


def ordinals(record):
    component = _component(record)
    return tuple(component.select('Pattern/Pads/Pad')) if component is not None else ()


def geometry_values(record):
    component = _component(record)
    return values(record) + (tuple((pad, name) for pad in component.select('Pattern/Pads/Pad')
                                   for name in ('X', 'Y')) if component is not None else ())


def _derived(name, kind, getter, *, value_dependencies=values, **options):
    return Field(name, kind, getter=getter, value_dependencies=value_dependencies,
                 reference_dependencies=references, collection_dependencies=collections,
                 ordinal_dependencies=ordinals, **options)


PAD_GROUP = _derived('InternalConnection', 'integer', group_number,
    description='Calculated connection-group position; labels and authored pairs define membership.')
POLICY = Record('PcbInternalConnectionPolicy', {
    'Pad': replace(reference_field('Pad', ROLE), description=
        'A member selecting the connected group. Serialization preserves the group policy; '
        'the representative member can be canonicalized when reading a file.'),
    'ConnectAll': Field('ConnectAll', 'boolean', default=False),
    'Id': _derived('Id', 'integer', lambda policy: group_number(linked(policy, ROLE))
                   if linked(policy, ROLE) is not None else -1),
    'Members': _derived('Members', 'tuple', members, item_kind='reference', nullable=True),
    'Ratlines': _derived('Ratlines', 'tuple', display_tree, nullable=True,
                         item_kind='tuple', value_dependencies=geometry_values),
})
POLICIES = Record('PcbInternalConnectionPolicies', {}, children={
    'IntCon': Child('IntCon', POLICY.name, maximum=None),
})


def definition(node):
    parent = node.parent
    if parent is not None and parent.kind == 'Component' and node.kind == 'InternalConnections':
        return POLICIES
    if (parent is not None and parent.kind == 'InternalConnections' and node.kind == 'IntCon'
            and parent.parent is not None and parent.parent.kind == 'Component'):
        return POLICY
    return None


def validate_component(document, component):
    if component is None:
        return
    policies = component.select('InternalConnections/IntCon')
    if not policies:
        return
    topology = groups(component, strict=False)
    by_pad = {pad: index for index, group in enumerate(topology) for pad in group}
    occupied = set()
    for policy in policies:
        pad = linked(policy, ROLE)
        # A newly attached policy can be assigned its selector afterward.
        if pad is None:
            continue
        if pad not in by_pad:
            raise ReferenceError('connection policy requires a pad in a connected group')
        number = by_pad[pad]
        if number in occupied:
            raise ReferenceError('connected pad group already has a policy; remove or retarget one before merging')
        occupied.add(number)


def validate_reference(document, reference, target):
    if reference.role == ROLE:
        component = owner(reference.source)
        if (reference.source.schema is not POLICY or target.kind != 'Pad'
                or component is None or component_of(target) is not component):
            raise ReferenceError('connection policy requires a pad in its own component')
    elif reference.role in internal_connections.ROLES:
        component = reference.source.parent.parent if reference.source.parent is not None else None
    else:
        return
    if document._automatic_structure:
        with preview_references(document.references, {reference.uid: replace(reference, target=target)}):
            validate_component(document, component)


def validate_removal(document, reference):
    if reference.role in internal_connections.ROLES:
        with preview_references(document.references, {reference.uid: None}):
            validate_component(document, reference.source.parent.parent)


def validate_references(document, references):
    for reference in references:
        validate_reference(document, reference, reference.target)


def effective(component, *, default_connect_all=False):
    """Return each current group with its explicit policy or the default False."""
    POLICY.fields['ConnectAll'].validate(default_connect_all)
    validate_component(component._owner(), component)
    topology = groups(component)
    if any(linked(policy, ROLE) is None for policy in component.select('InternalConnections/IntCon')):
        raise ReferenceError('connection policy requires a selected pad group')
    settings = {linked(policy, ROLE): policy['ConnectAll']
                for policy in component.select('InternalConnections/IntCon')}
    return tuple((group, next((settings[pad] for pad in group if pad in settings), default_connect_all))
                 for group in topology)
