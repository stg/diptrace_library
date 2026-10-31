"""Authored pad-pair definitions, separate from calculated connection groups."""
from ...common.references import ReferenceError
from ...common.schema import Child, Field, Record
from .membership import component_of
from .relationships import linked, reference_field


ROLES = ('internal-pad-1', 'internal-pad-2')


def _position(name, role):
    return Field(name, 'integer',
        getter=lambda node: pad._ordinal()+1 if (pad := linked(node, role)) is not None else -1,
        reference_dependencies=lambda node: ((node, role, 'outgoing'),),
        ordinal_dependencies=lambda node: (pad,) if (pad := linked(node, role)) is not None else ())


PAIR = Record('PcbInternalConnectionDefinition', {
    'Pad1': reference_field('Pad1', ROLES[0]),
    'Pad2': reference_field('Pad2', ROLES[1]),
    'X': _position('X', ROLES[0]),
    'Y': _position('Y', ROLES[1]),
}, parameters=('X', 'Y'))
DEFINITIONS = Record('PcbInternalConnectionDefinitions', {}, children={
    'Item': Child('Item', PAIR.name, maximum=None),
})


def definition(node):
    parent = node.parent
    if parent is not None and parent.kind == 'Component' and node.kind == 'IntConRecords':
        return DEFINITIONS
    if (parent is not None and parent.kind == 'IntConRecords' and node.kind == 'Item'
            and parent.parent is not None and parent.parent.kind == 'Component'):
        return PAIR
    return None


def validate_reference(document, reference, target):
    if reference.role not in ROLES:
        return
    source = reference.source
    owner = source.parent.parent if source.parent is not None else None
    placed = (owner is not None and owner.kind == 'Component'
              and source.parent.kind == 'IntConRecords' and component_of(target) is owner)
    from .library_records import is_pattern
    cached = (owner is not None and is_pattern(owner) and source.parent.kind == 'InternalConnections'
              and target.parent is owner.child('Pads'))
    if (source.schema is not PAIR or target.kind != 'Pad' or not (placed or cached)
            or target._owner() is not document):
        raise ReferenceError('internal connection requires a pad in its own component or definition')
    if any(link.uid != reference.uid for link in document.references.outgoing(source, role=reference.role)):
        raise ReferenceError('internal connection endpoint already has a pad')


def validate_references(document, references):
    for reference in references:
        validate_reference(document, reference, reference.target)
