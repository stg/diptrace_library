"""Named assembly choices and component exclusions over current identities."""
from dataclasses import replace

from ...common.references import ReferenceError
from ...common.schema import Child, Field, Record
from .relationships import optional_reference_fields


EXCLUSION_ROLE = 'assembly-exclusion'
TABLE_ROLE = 'table-assembly-variant'
VARIANT = Record('PcbAssemblyVariant', {
    'Name': Field('Name', 'text', required=True, default=''),
    'Id': Field('Id', 'integer', getter=lambda node: node._ordinal(), ordinal_dependencies=lambda node: (node,)),
}, parameters=('Name',))
VARIANTS = Record('PcbAssemblyVariants', {}, children={
    'AssemblyVariant': Child('AssemblyVariant', VARIANT.name, maximum=None)})
MEMBER = Record('PcbAssemblyExclusion', optional_reference_fields('Variant', 'Index', EXCLUSION_ROLE),
                parameters=('Index',))
EXCLUSIONS = Record('PcbAssemblyExclusions', {}, children={'Item': Child('Item', MEMBER.name, maximum=None)})


def _table_fields():
    fields = optional_reference_fields('Variant', 'AssemblyVariant', TABLE_ROLE)
    position = fields['AssemblyVariant']
    def choices(node):
        if (document := node._owner()) is None:
            return ()
        board = document.one('/Board')
        variants = board.child('AssemblyVariants')
        return ((board, 'AssemblyVariants'),) + (((variants, 'AssemblyVariant'),) if variants is not None else ())
    def current_index(node):
        index = position.getter(node)
        # The unused zero in a document without named choices does not imply
        # an invented default variant. Variant is still None in that case.
        if index < 0 and node.child('UnresolvedAssemblyVariant') is None:
            document = node._owner()
            variants = document.one('/Board').child('AssemblyVariants') if document is not None else None
            if variants is None or not variants.children('AssemblyVariant'):
                return 0
        return index
    fields['AssemblyVariant'] = replace(position, getter=current_index,
        collection_dependencies=lambda node: position.collection_dependencies(node)+choices(node))
    return fields


TABLE_FIELDS = _table_fields()


def definition(node):
    parent = node.parent
    if parent is None:
        return None
    if node.kind == 'AssemblyVariants' and parent.kind == 'Board':
        return VARIANTS
    if node.kind == 'AssemblyVariant' and parent.kind == 'AssemblyVariants':
        return VARIANT
    if node.kind == 'AssemblyExclude' and parent.kind == 'Component':
        return EXCLUSIONS
    if node.kind == 'Item' and parent.kind == 'AssemblyExclude':
        return MEMBER
    return None


def validate_reference(document, reference, target):
    if reference.role not in (EXCLUSION_ROLE, TABLE_ROLE):
        return
    board, source = document.one('/Board'), reference.source
    if reference.role == EXCLUSION_ROLE:
        component = source.parent.parent if source.parent is not None else None
        valid = (source.schema is MEMBER and component is not None and component.kind == 'Component'
                 and source.parent is component.child('AssemblyExclude') and component.parent is board.child('Components'))
    else:
        table = source.parent
        valid = (source.kind == 'AutoUpdate' and table is not None and table.kind == 'Table'
                 and table.parent is board.child('Tables'))
    if not valid or target.schema is not VARIANT or target.parent is not board.child('AssemblyVariants'):
        raise ReferenceError('assembly selection requires a named variant in its own PCB')
    if any(link.uid != reference.uid for link in document.references.outgoing(source, role=reference.role)):
        raise ReferenceError('assembly selection already has a target')


def validate_references(document, references):
    for reference in references:
        validate_reference(document, reference, reference.target)


def validate_move(document, node, parent):
    board = document.one('/Board')
    if node.schema is VARIANTS:
        valid = parent is board
    elif node.schema is VARIANT:
        valid = parent is board.child('AssemblyVariants')
    elif node.schema is EXCLUSIONS:
        valid = parent.kind == 'Component' and parent.parent is board.child('Components')
    elif node.schema is MEMBER:
        valid = (parent.kind == 'AssemblyExclude' and parent.parent is not None
                 and parent.parent.kind == 'Component' and parent.parent.parent is board.child('Components'))
    else:
        return
    if not valid:
        raise ReferenceError('assembly data must remain in its PCB scope')


def requires_attachment(parent, node):
    return (node.schema in (VARIANTS, VARIANT, EXCLUSIONS, MEMBER) or
            (parent.kind, node.kind) in (('Board', 'AssemblyVariants'), ('AssemblyVariants', 'AssemblyVariant'),
                                        ('Component', 'AssemblyExclude'), ('AssemblyExclude', 'Item')))


def prepare_attachment(node):
    if definition(node) is not None:
        for child in node.walk(include_self=True):
            if (schema := definition(child)) is not None:
                if schema is MEMBER and child.schema is None and child.arguments:
                    raise TypeError('assembly indices are calculated; assign Variant after attachment')
                child.bind_schema(schema)
