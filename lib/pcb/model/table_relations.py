"""Component identities selected by documentation-table rows.

The stored row text is authored content. A component selection identifies the
source of that content; changing it does not regenerate a BOM or placement table.
"""
from ...common.references import ReferenceError
from ...common.structural_edits import assembly
from ...common.reference_edits import resolve_unavailable_reference


ROLE = 'table-component'
MISSING = 'UnresolvedComponentIndex'


def reference_dependencies(member):
    return ((member, ROLE, 'outgoing'),)


def value_dependencies(member):
    return ((member, MISSING),) if member.child(MISSING) is not None else ()


def collection_dependencies(member):
    return ((member, MISSING),)


def _target(member):
    document = member._owner()
    links = document.references.outgoing(member, role=ROLE) if document else ()
    if len(links) > 1:
        raise ReferenceError('table row component has multiple targets')
    return links[0].target if links else None


def component(member):
    target = _target(member)
    if target is None and member.child(MISSING) is not None:
        raise ReferenceError('table row component has an unresolved target')
    return target


def component_index(member):
    target = _target(member)
    return target._ordinal() if target is not None else member.get(MISSING, -1)


def ordinal_dependencies(member):
    target = _target(member)
    return (target,) if target is not None else ()


def table_of(member):
    row = member.parent
    rows = row.parent if row is not None else None
    table = rows.parent if rows is not None else None
    return table if (member.kind == 'Item' and row is not None and row.kind == 'Row'
        and rows is not None and rows.kind == 'RowComponents'
        and table is not None and table.kind == 'Table') else None


def validate_reference(document, reference, target):
    if reference.role != ROLE:
        return
    from .table_records import MEMBER
    source = reference.source
    table, board = table_of(source), document.one('/Board')
    if (source.schema is not MEMBER or table is None or table.parent is not board.child('Tables')
            or not table['Enabled'] or target.kind != 'Component'
            or target.parent is not board.child('Components') or not target['Enabled']):
        raise ReferenceError('table row requires an enabled component in its own PCB')
    if any(link.uid != reference.uid for link in document.references.outgoing(source, role=ROLE)):
        raise ReferenceError('table row component already has a target')


def validate_references(document, references):
    for reference in references:
        validate_reference(document, reference, reference.target)


def validate_field(document, owner, name):
    if owner.kind == 'Table' and name == 'Enabled':
        validate_references(document,
            document.references._content_references(owner.walk(include_self=True)))


def validate_move(document, node, parent):
    from .table_records import MEMBER, ROW, ROWS, TABLE
    if node.schema is MEMBER:
        valid = parent.schema is ROW
    elif node.schema is ROW:
        valid = parent.schema is ROWS
    elif node.schema is ROWS:
        valid = parent.schema is TABLE
    elif node.schema is TABLE:
        valid = parent is document.one('/Board').child('Tables')
    else:
        return
    if not valid or parent._owner() is not document:
        raise ReferenceError('table component rows must remain in PCB tables')


def prepare_attachment(root):
    from .table_records import MEMBER, definition
    if root.kind not in ('Table', 'RowComponents', 'Row', 'Item'):
        return
    for node in root.walk(include_self=True):
        if definition(node) is MEMBER and node.schema is None and node.arguments:
            raise TypeError('ComponentIndex is calculated; assign Component after attaching the row')


def set_component(member, target):
    """Retarget, disconnect or explicitly resolve an unknown component slot."""
    from .relationships import assign
    document = member._owner()
    if document is None:
        raise ReferenceError('attach the row to a PCB before assigning its component')
    missing = member.child(MISSING)
    if missing is None:
        assign(member, ROLE, target)
        return

    resolve_unavailable_reference(member, target, role=ROLE, missing=missing)
