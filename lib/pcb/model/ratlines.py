"""Supplied ratline geometry and pad identities, without routing calculation."""
from ...common.references import ReferenceError
from ...common.schema import Child, Field, Record
from .membership import component_of
from .pad_links import pad_fields


ROLES = ('ratline-pad-1', 'ratline-pad-2')
RATLINE = Record('PcbRatline', {
    'Id': Field('Id', 'integer', getter=lambda row: row._ordinal(), ordinal_dependencies=lambda row: (row,)),
    'Enabled': Field('Enabled', 'boolean', default=True),
    'Hidden': Field('Hidden', 'boolean', default=False),
    **{name: Field(name, 'number', default=0, unit='shared length') for name in ('X1', 'Y1', 'X2', 'Y2')},
    **{name: field for end, role in enumerate(ROLES, 1) for name, field in pad_fields(end, role).items()},
})
RATLINES = Record('PcbRatlines', {}, children={'Ratline': Child('Ratline', RATLINE.name, maximum=None)})


def definition(node):
    parent = node.parent
    if parent is not None:
        if node.kind == 'Ratlines' and parent.kind == 'Board':
            return RATLINES
        if node.kind == 'Ratline' and parent.kind == 'Ratlines':
            return RATLINE
    return None


def validate_reference(document, reference, target):
    if reference.role not in ROLES:
        return
    source, component = reference.source, component_of(target)
    if (source.schema is not RATLINE or source.parent is not document.one('/Board').child('Ratlines')
            or target.kind != 'Pad' or component is None or target._owner() is not document
            or component.parent is not document.one('/Board').child('Components') or not component['Enabled']):
        raise ReferenceError('ratline endpoint requires a placed pad in this PCB')
    if any(link.uid != reference.uid for link in document.references.outgoing(source, role=reference.role)):
        raise ReferenceError('ratline endpoint already has a target')


def validate_references(document, references):
    for reference in references:
        validate_reference(document, reference, reference.target)


def validate_move(document, node, parent):
    if node.schema is RATLINES:
        valid = parent is document.one('/Board')
    elif node.schema is RATLINE:
        valid = parent is document.one('/Board').child('Ratlines')
    else:
        return
    if not valid:
        raise ReferenceError('ratlines must remain in their PCB board collection')


def requires_attachment(parent, node):
    return (node.schema in (RATLINE, RATLINES) or parent.schema is RATLINES and node.kind == 'Ratline'
            or parent.kind == 'Board' and node.kind == 'Ratlines')


def prepare_attachment(node):
    if (schema := definition(node)) is not None:
        node.bind_schema(schema)
        if schema is RATLINES:
            for child in node.children('Ratline'):
                child.bind_schema(RATLINE)
