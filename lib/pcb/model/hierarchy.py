"""PCB links to named schematic block instances.

Placed RefDes text is independent of these persistent identities. In particular,
an underscore in a name does not establish a hierarchy relationship.
"""
from ...common.references import ReferenceError
from . import hierarchy_records as records


BLOCK_ROLE = 'schematic-hierarchy-block'


def linkage_path(component):
    """Return the complete schematic identity path from the current model.

    HierarchyPath stores the ordered block steps. The component's own schematic
    identity is appended when a file representation needs the complete chain.
    """
    path = component.child('HierarchyPath')
    steps = tuple(item['Id'] for item in path._child_sequence('Item')) if path is not None else ()
    return (*steps, component['HiddenId']) if steps else ()


def _blocks(document):
    sheets = document.one('/Board').child('HierarchySheets')
    if sheets is not None:
        for sheet in sheets._child_sequence('HSheet'):
            if (blocks := sheet.child('UpdateIds')) is not None:
                yield from blocks._child_sequence('UId')


def _validate_key(document, block):
    if any(other is not block and other['Id'] == block['Id'] for other in _blocks(document)):
        raise ReferenceError(f"duplicate schematic hierarchy block Id {block['Id']}")


def validate_reference(document, reference, target):
    if reference.role != BLOCK_ROLE:
        return
    source = reference.source
    path = source.parent
    component = path.parent if path is not None else None
    board = document.one('/Board')
    blocks = target.parent
    sheet = blocks.parent if blocks is not None else None
    if (source.schema is not records.PATH_ITEM or path is None or path.schema is not records.PATH
            or component is None or component.kind != 'Component'
            or component.parent is not board.child('Components')
            or target.schema is not records.BLOCK or blocks is None or blocks.schema is not records.BLOCKS
            or sheet is None or sheet.schema is not records.SHEET
            or sheet.parent is not board.child('HierarchySheets')):
        raise ReferenceError('hierarchy step requires a block in this PCB hierarchy table')
    if component['HiddenId'] < 0 or component.one('Pattern')['Type'] in (15, 16):
        raise ReferenceError('this component has no schematic hierarchy link')
    if any(link.uid != reference.uid for link in document.references.outgoing(source, role=BLOCK_ROLE)):
        raise ReferenceError('hierarchy step already has a block')
    _validate_key(document, target)


def validate_field(document, node, name):
    if node.schema is records.BLOCK and name == 'Id':
        _validate_key(document, node)
    component = node if node.kind == 'Component' else node.parent if node.kind == 'Pattern' else None
    if component is not None and (name == 'HiddenId' or node.kind == 'Pattern' and name == 'Type'):
        path = component.child('HierarchyPath')
        if path is not None and path._child_sequence('Item') and (
                component['HiddenId'] < 0 or component.one('Pattern')['Type'] in (15, 16)):
            raise ReferenceError('clear the hierarchy path before removing the schematic link')


def validate_move(document, node, parent):
    if node.schema is records.SHEET:
        if parent is not document.one('/Board').child('HierarchySheets'):
            raise ReferenceError('hierarchy sheets must remain in the PCB hierarchy table')
        proposed = node.select('UpdateIds/UId')
        seen = {block['Id'] for block in _blocks(document) if block not in proposed}
        for block in proposed:
            if block['Id'] in seen:
                raise ReferenceError(f"duplicate schematic hierarchy block Id {block['Id']}")
            seen.add(block['Id'])
    elif node.schema is records.BLOCK:
        sheet = parent.parent
        if (parent.schema is not records.BLOCKS or sheet is None or sheet.schema is not records.SHEET
                or sheet.parent is not document.one('/Board').child('HierarchySheets')):
            raise ReferenceError('hierarchy blocks require a PCB hierarchy sheet')
        _validate_key(document, node)


def validate_references(document, references):
    for reference in references:
        validate_reference(document, reference, reference.target)
