"""A PCB title cell selects one styled content identity in its own grid."""
from ...common.references import ReferenceError
from ...common.reference_edits import resolve_unavailable_reference


ROLE = 'title-cell-field'
MISSING = 'UnresolvedFieldId'


def grid_of(node):
    parent = node.parent
    grid = parent.parent if parent is not None else None
    return grid if (parent is not None and parent.kind in ('Cells', 'Contents')
                    and grid is not None and grid.kind == 'TitleBlock') else None


def _target(cell):
    document = cell._owner()
    links = document.references.outgoing(cell, role=ROLE) if document is not None else ()
    if len(links) > 1:
        raise ReferenceError('title cell has multiple fields')
    return links[0].target if links else None


def field(cell):
    if cell.child(MISSING) is not None:
        raise ReferenceError('title cell field is unresolved')
    return _target(cell)


def field_id(cell):
    target = _target(cell)
    return target._ordinal() if target is not None else cell.get(MISSING, -1)


def set_field(cell, target):
    if cell._owner() is None:
        raise ReferenceError('attach the title cell before selecting its field')
    missing = cell.child(MISSING)
    if missing is None:
        from .relationships import assign
        assign(cell, ROLE, target)
    else:
        resolve_unavailable_reference(cell, target, role=ROLE, missing=missing)


def dependencies(cell):
    return ((cell, ROLE, 'outgoing'),)


def ordinals(cell):
    target = _target(cell)
    return (target,) if target is not None else ()


def values(cell):
    return ((cell, MISSING),) if cell.child(MISSING) is not None else ()


def collections(cell):
    return ((cell, MISSING),)


def validate_reference(document, reference, target):
    if reference.role != ROLE:
        return
    from .title_records import CELL
    source = reference.source
    grid = grid_of(source)
    sheet = document.one('/Board').child('SheetSettings')
    titles = sheet.child('TitleBlocks') if sheet is not None else None
    if (source.schema is not CELL or grid is None or grid.parent is not titles
            or target.kind != 'Content' or target.parent is not grid.child('Contents')
            or source.child(MISSING) is not None):
        raise ReferenceError('title cell requires a field from its own grid')
    if any(link.uid != reference.uid for link in document.references.outgoing(source, role=ROLE)):
        raise ReferenceError('title cell already has a field')


def validate_references(document, references):
    for reference in references:
        validate_reference(document, reference, reference.target)


def validate_move(document, node, parent):
    from .title_records import CELL, CONTENT, BLOCK, BLOCKS, CELLS, CONTENTS
    if node.schema not in (CELL, CONTENT, BLOCK, BLOCKS, CELLS, CONTENTS):
        return
    valid = True
    if node.schema is CELL:
        valid = parent.schema is CELLS
    elif node.schema is CONTENT:
        valid = parent.schema is CONTENTS
    elif node.schema in (CELLS, CONTENTS):
        valid = parent.schema is BLOCK
    elif node.schema is BLOCK:
        valid = parent.schema is BLOCKS
    elif node.schema is BLOCKS:
        valid = parent is document.one('/Board').child('SheetSettings')
    if not valid or parent._owner() is not document:
        raise ReferenceError('title data must remain inside PCB sheet title grids')


def prepare_attachment(node):
    from .title_records import CELL, definition
    if node.kind not in ('TitleBlocks', 'TitleBlock', 'Cells', 'Contents', 'Cell', 'Content'):
        return
    for child in node.walk(include_self=True):
        if child.schema is None and definition(child) is CELL and child.arguments:
            raise TypeError('title FieldId is calculated; select Field after attaching the cell')
