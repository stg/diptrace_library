"""Named access to PCB identity roles, shared by its model record families."""
from ...common.references import ReferenceError
from ...common.schema import Field
from ...common.reference_edits import resolve_unavailable_reference


def linked(source, role):
    document = source._owner()
    links = document.references.outgoing(source, role=role) if document else ()
    if len(links) > 1:
        raise ReferenceError(f'{role}: multiple targets')
    if document and any(issue.message.startswith(role+':')
                        for issue in document.references._source_issues(source)):
        raise ReferenceError(f'{role}: unresolved target')
    return links[0].target if links else None


def assign(source, role, target):
    document = source._owner()
    if document is None:
        raise ReferenceError('attach the record to a PCB before assigning a relationship')
    current = linked(source, role)
    if current is target:
        return
    links = document.references.outgoing(source, role=role)
    if target is None:
        if links:
            document.references.discard(links[0])
    elif links:
        document.references.retarget(links[0], target)
    else:
        document.references.bind(source, target, role=role)


def reference_field(name, role):
    return Field(name, 'reference', nullable=True,
        getter=lambda node: linked(node, role), setter=lambda node, value: assign(node, role, value),
        reference_dependencies=lambda node: ((node, role, 'outgoing'),))


def index_field(name, role, *, offset=0):
    return Field(name, 'integer',
        getter=lambda node: target._ordinal()+offset if (target := linked(node, role)) is not None else -1,
        ordinal_dependencies=lambda node: (target,) if (target := linked(node, role)) is not None else (),
        reference_dependencies=lambda node: ((node, role, 'outgoing'),))


def optional_reference_fields(name, index, role):
    """A nullable identity with a derived index or one explicit unresolved index."""
    missing = 'Unresolved'+index
    dependencies = dict(reference_dependencies=lambda node: ((node, role, 'outgoing'),),
        collection_dependencies=lambda node: ((node, missing),),
        value_dependencies=lambda node: ((node, missing),) if node.child(missing) is not None else ())
    def selected(node):
        if node.child(missing) is not None:
            raise ReferenceError(f'{role}: unresolved target')
        return linked(node, role)
    def set_selected(node, target):
        unavailable = node.child(missing)
        if unavailable is None:
            assign(node, role, target)
        else:
            resolve_unavailable_reference(node, target, role=role, missing=unavailable)
    def position(node):
        if node.child(missing) is not None:
            return node[missing]
        target = selected(node)
        return target._ordinal() if target is not None else -1
    return {
        name: Field(name, 'reference', nullable=True, getter=selected, setter=set_selected, **dependencies),
        index: Field(index, 'integer', getter=position,
            ordinal_dependencies=lambda node: (target,) if node.child(missing) is None
                and (target := selected(node)) is not None else (), **dependencies),
        missing: Field(missing, 'integer'),
    }
