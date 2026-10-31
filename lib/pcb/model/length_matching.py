"""Length-matching policies and selected connections, independent of routing."""
from dataclasses import replace
from decimal import Decimal

from ...common.references import ReferenceError
from ...common.reference_edits import preview_references
from ...common.schema import Child, Field, Record
from .membership import component_of, get_net
from .relationships import linked, reference_field, index_field
from .pad_links import pad_fields


NET_ROLE = 'length-rule-net'
CLASS_ROLE = 'length-rule-class'
PAD_ROLES = ('length-rule-pad-1', 'length-rule-pad-2')
DEFAULT_FIXED_LENGTH = -1
DEFAULT_DELTA = Decimal('7.62')


CONNECTION = Record('PcbLengthConnection', {
    'Net': reference_field('Net', NET_ROLE), 'NetId': index_field('NetId', NET_ROLE),
    **{name: field for end, role in enumerate(PAD_ROLES, 1) for name, field in pad_fields(end, role).items()},
    'Length': Field('Length', 'number', default=0, unit='shared length'),
    'Error': Field('Error', 'boolean', default=False),
})
CONNECTIONS = Record('PcbLengthConnections', {}, children={
    'Rule': Child('Rule', CONNECTION.name, maximum=None)})


def _rows(policy):
    rows = policy.child('Rules')
    return rows._child_sequence('Rule') if rows is not None else ()


def _error_field():
    return Field('AnyError', 'boolean', getter=lambda policy: any(row['Error'] for row in _rows(policy)),
        value_dependencies=lambda policy: ((row, 'Error') for row in _rows(policy)),
        collection_dependencies=lambda policy: ((policy, 'Rules'),) +
            (((rows, 'Rule'),) if (rows := policy.child('Rules')) is not None else ()),
        description='Aggregate of the stored connection error results; does not calculate route length.')


POLICY = Record('PcbLengthRule', {
    'Name': Field('Name', 'text', default=''),
    'FixedLength': Field('FixedLength', 'number', default=DEFAULT_FIXED_LENGTH, unit='shared length'),
    'Delta': Field('Delta', 'number', default=DEFAULT_DELTA, unit='shared length'),
    'AnyError': _error_field(),
    'Class': replace(reference_field('Class', CLASS_ROLE),
        description='Optional class selection of MainLengthRule; its working name, limits and connections remain independent.'),
    'NetClass': index_field('NetClass', CLASS_ROLE),
}, children={'Rules': Child('Rules', CONNECTIONS.name)})
POLICIES = Record('PcbLengthRules', {}, children={
    'LengthRule': Child('LengthRule', POLICY.name, maximum=None)})
RESULTS = Record('PcbClassLengthResults', {
    'AnyError': _error_field(),
}, children={'Rules': Child('Rules', CONNECTIONS.name)})

_OWNERS = ('MainLengthRule', 'LengthRule', 'LengthResults')
_SCHEMAS = (POLICY, POLICIES, RESULTS, CONNECTION, CONNECTIONS)


def policy_owners(board, *, classes=None):
    """Current ordered owners for generated class policies followed by user rules.

    A class can have a policy without stored calculation results. Its settings
    still occupy their position. The separate main rule is outside this list.
    Writers and saved-check selector views use the same ordering.
    """
    classes = board.select('NetClasses/NetClass') if classes is None else classes
    return tuple(net_class for net_class in classes
                 if net_class.get('CheckLength', False)) + tuple(board.select('LengthRules/LengthRule'))


def connection_position(row):
    """Derive a saved-check selection from a current connection identity."""
    owner = row.parent.parent
    owner = owner.parent if owner.kind == 'LengthResults' else owner
    owners = policy_owners(row._owner().one('/Board'))
    return owners.index(owner) if owner in owners else -1, row._ordinal()


def definition(node):
    parent = node.parent
    if parent is None:
        return None
    if parent.kind == 'Board':
        return POLICY if node.kind == 'MainLengthRule' else POLICIES if node.kind == 'LengthRules' else None
    if parent.kind == 'LengthRules' and node.kind == 'LengthRule':
        return POLICY
    if parent.kind == 'NetClass' and node.kind == 'LengthResults':
        return RESULTS
    if parent.kind in _OWNERS and node.kind == 'Rules':
        return CONNECTIONS
    if parent.kind == 'Rules' and node.kind == 'Rule' and parent.parent is not None:
        return CONNECTION if parent.parent.kind in _OWNERS else None
    return None


def _policy_in(document, policy):
    board = document.one('/Board')
    valid = (policy.kind == 'MainLengthRule' and policy.parent is board or
             policy.kind == 'LengthRule' and policy.parent is not None and
             policy.parent.kind == 'LengthRules' and policy.parent.parent is board or
             policy.kind == 'LengthResults' and policy.parent is not None and
             policy.parent.kind == 'NetClass' and policy.parent.parent is board.child('NetClasses'))
    if not valid:
        raise ReferenceError('length rule must belong to this PCB')


def _connection_in(document, connection):
    parent = connection.parent
    if connection.kind != 'Rule' or parent is None or parent.kind != 'Rules' or parent.parent is None:
        raise ReferenceError('length connection must belong to a length rule')
    _policy_in(document, parent.parent)


def _net_in(document, net):
    if (net.kind != 'Net' or net.parent is not document.one('/Board/Nets')
            or not net.get('Enabled', True)):
        raise ReferenceError('length connection requires an enabled net in this PCB')


def _validate_pad(document, row, pad):
    component = component_of(pad)
    if (pad._owner() is not document or component is None or
            component.parent is not document.one('/Board/Components') or not component.get('Enabled', True)):
        raise ReferenceError('length connection requires a placed pad in this PCB')
    if (net := linked(row, NET_ROLE)) is None or get_net(pad) is not net:
        raise ReferenceError('length connection pad must belong to its selected net')


def _validate_connection(document, row):
    _connection_in(document, row)
    net = linked(row, NET_ROLE)
    if net is not None:
        _net_in(document, net)
        policy = row.parent.parent
        if policy.kind == 'LengthResults' and linked(net, 'net-class') is not policy.parent:
            raise ReferenceError('class length connection requires a net assigned to its owning class')
    for role in PAD_ROLES:
        if (pad := linked(row, role)) is not None:
            _validate_pad(document, row, pad)


def validate_reference(document, reference, target):
    if reference.role == CLASS_ROLE:
        board = document.one('/Board')
        if (reference.source.kind != 'MainLengthRule' or reference.source.parent is not board
                or target.kind != 'NetClass' or target.parent is not board.child('NetClasses')):
            raise ReferenceError('only the main working length rule can select a class in this PCB')
        if any(link.uid != reference.uid for link in document.references.outgoing(reference.source, role=CLASS_ROLE)):
            raise ReferenceError('main working length rule already has a selected class')
        return
    if reference.role == 'net-class' and reference.source.kind == 'Net':
        with preview_references(document.references, {reference.uid: replace(reference, target=target)}):
            _check_net_class(document, reference.source)
        return
    if reference.role not in (NET_ROLE, *PAD_ROLES):
        return
    _connection_in(document, reference.source)
    if any(link.uid != reference.uid for link in document.references.outgoing(reference.source, role=reference.role)):
        raise ReferenceError(f'{reference.role}: connection already has a target')
    if reference.role == NET_ROLE:
        _net_in(document, target)
        with preview_references(document.references, {reference.uid: replace(reference, target=target)}):
            _validate_connection(document, reference.source)
    else:
        _validate_pad(document, reference.source, target)


def validate_removal(document, reference):
    if reference.role == NET_ROLE:
        with preview_references(document.references, {reference.uid: None}):
            _validate_connection(document, reference.source)
    elif reference.role == 'net-class' and reference.source.kind == 'Net':
        with preview_references(document.references, {reference.uid: None}):
            _check_net_class(document, reference.source)


def _check_net_class(document, net):
    for reference in document.references.incoming(net, role=NET_ROLE):
        _validate_connection(document, reference.source)


def check_pad_net(document, pad, net):
    for reference in document.references.incoming(pad):
        if reference.role in PAD_ROLES and linked(reference.source, NET_ROLE) is not net:
            raise ReferenceError('net change would contradict a length connection; edit its pad target first')


def validate_references(document, references):
    for reference in references:
        validate_reference(document, reference, reference.target)


def validate_move(document, node, parent):
    if node.schema not in _SCHEMAS:
        return
    if node.schema is POLICY:
        valid = (node.kind == 'MainLengthRule' and parent is document.one('/Board') or
                 node.kind == 'LengthRule' and parent.kind == 'LengthRules' and parent.parent is document.one('/Board'))
    elif node.schema is POLICIES:
        valid = node.kind == 'LengthRules' and parent is document.one('/Board')
    elif node.schema is RESULTS:
        valid = (node.kind == 'LengthResults' and parent.kind == 'NetClass' and
                 parent.parent is document.one('/Board').child('NetClasses'))
    elif node.schema is CONNECTION:
        valid = parent.kind == 'Rules' and parent.parent is not None
        if valid:
            _policy_in(document, parent.parent)
    else:
        valid = node.kind == 'Rules' and parent.kind in _OWNERS
        if valid:
            _policy_in(document, parent)
    if not valid:
        raise ReferenceError('length-rule data must remain in its PCB rule scope')


def prepare_attachment(node):
    if definition(node) is None:
        return
    for record in node.walk(include_self=True):
        if (schema := definition(record)) is not None:
            record.bind_schema(schema)


def requires_attachment(parent, node):
    return (node.schema in _SCHEMAS or
            (parent.schema, node.kind) in ((POLICIES, 'LengthRule'), (POLICY, 'Rules'),
                                          (RESULTS, 'Rules'), (CONNECTIONS, 'Rule')) or
            parent.kind == 'NetClass' and node.kind == 'LengthResults' or
            parent.kind == 'Board' and node.kind in ('MainLengthRule', 'LengthRules'))
