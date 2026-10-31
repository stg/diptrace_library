"""Supplied teardrop polygons and the traces that use them."""
from ...common.drawing_records import POINTS, POINT
from ...common.references import ReferenceError
from ...common.schema import Child, Field, Record
from .board_rules import LAYER_FIELDS
from .relationships import reference_field, index_field


ROLE = 'trace-teardrop'
TEARDROP = Record('PcbTeardrop', {
    'Id': Field('Id', 'integer', getter=lambda node: node._ordinal(), ordinal_dependencies=lambda node: (node,)),
    **LAYER_FIELDS,
    **{name: Field(name, 'number', default=0, unit='shared length') for name in ('DrawX', 'DrawY')},
}, parameters=('Id',), children={'Points': Child('Points', POINTS.name)})
TEARDROPS = Record('PcbTeardrops', {}, children={'Teardrop': Child('Teardrop', TEARDROP.name, maximum=None)})
MEMBER = Record('PcbTraceTeardrop', {
    'Teardrop': reference_field('Teardrop', ROLE),
    'Index': index_field('Index', ROLE),
}, parameters=('Index',))
MEMBERS = Record('PcbTraceTeardrops', {}, children={'Item': Child('Item', MEMBER.name, maximum=None)})


def net_of(node):
    while node is not None and node.kind != 'Net':
        node = node.parent
    return node


def _net(document, node):
    net = net_of(node)
    return net if net is not None and net.parent is document.one('/Board').child('Nets') and net['Enabled'] else None


def definition(node):
    parent = node.parent
    if parent is None:
        return None
    if node.kind == 'Teardrops' and parent.kind == 'Net':
        return TEARDROPS
    if node.kind == 'Teardrop' and parent.kind == 'Teardrops':
        return TEARDROP
    if node.kind == 'Points' and parent.kind == 'Teardrop':
        return POINTS
    if node.kind == 'pt' and parent.kind == 'Points' and parent.parent.kind == 'Teardrop':
        return POINT
    if node.kind == 'ConnectedTeardrops' and parent.kind == 'Trace':
        return MEMBERS
    if node.kind == 'Item' and parent.kind == 'ConnectedTeardrops':
        return MEMBER
    return None


def validate_reference(document, reference, target):
    if reference.role == 'copper-layer' and reference.source.schema is TEARDROP:
        if _net(document, reference.source) is None:
            raise ReferenceError('teardrop copper selection requires a supplied polygon in its PCB net')
        return
    if reference.role != ROLE:
        return
    source = reference.source
    net = _net(document, source)
    trace = source.parent.parent if source.parent is not None else None
    if (source.schema is not MEMBER or trace is None or trace.kind != 'Trace'
            or source.parent is not trace.child('ConnectedTeardrops') or net is None
            or target.schema is not TEARDROP or target.parent is not net.child('Teardrops')
            or target._owner() is not document):
        raise ReferenceError('trace teardrop must be a supplied polygon in the same PCB net')
    if any(link.uid != reference.uid for link in document.references.outgoing(source, role=ROLE)):
        raise ReferenceError('trace teardrop selection already has a target')


def validate_references(document, references):
    for reference in references:
        validate_reference(document, reference, reference.target)


def validate_move(document, node, parent):
    if node.schema is TEARDROPS:
        valid = parent.kind == 'Net' and _net(document, parent) is parent
    elif node.schema is TEARDROP:
        valid = parent.schema is TEARDROPS and _net(document, parent) is not None
    elif node.schema is MEMBERS:
        valid = parent.kind == 'Trace' and _net(document, parent) is not None
    elif node.schema is MEMBER:
        valid = parent.schema is MEMBERS and _net(document, parent) is not None
    else:
        return
    if not valid:
        raise ReferenceError('teardrop data must remain in its PCB net or trace collection')


def validate_field(document, node, name):
    if node.kind == 'Net' and name == 'Enabled':
        validate_references(document, document.references._content_references(node.walk(include_self=True)))


def requires_attachment(parent, node):
    return (node.schema in (TEARDROPS, TEARDROP, MEMBERS, MEMBER) or
            (parent.kind, node.kind) in (('Net', 'Teardrops'), ('Trace', 'ConnectedTeardrops')) or
            parent.schema is TEARDROPS and node.kind == 'Teardrop' or parent.schema is MEMBERS and node.kind == 'Item')


def prepare_attachment(node):
    for child in node.walk(include_self=True):
        if (schema := definition(child)) is not None:
            if schema in (TEARDROP, MEMBER) and child.schema is None and child.arguments:
                raise TypeError('teardrop IDs and selection indices are calculated; assign their named fields after attachment')
            child.bind_schema(schema)
