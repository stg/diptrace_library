"""Ownership and target constraints for PCB graphic relationships."""
from ...common.references import ReferenceError
from . import graphic_records


def validate_reference(document, reference, target):
    role = reference.role
    board = document.one('/Board')
    if role == 'pcb-group':
        group_field = reference.source.schema.fields.get('Group') if reference.source.schema is not None else None
        if group_field is None or group_field.kind != 'reference':
            raise ReferenceError('board group membership requires a board-level grouped object')
        collection, kind = 'Groups', 'Group'
    elif role == 'graphic-net':
        if reference.source.schema not in (graphic_records.SHAPE, graphic_records.POUR):
            raise ReferenceError('graphic net assignment requires a board drawing or copper pour')
        collection, kind = 'Nets', 'Net'
    elif role == 'drawing-layer':
        if reference.source.schema is not graphic_records.SHAPE:
            raise ReferenceError('drawing layer assignment requires a board drawing')
        collection = graphic_records.layer_scope(reference.source)
        if collection is None:
            raise ReferenceError('this drawing layer family has no layer target')
        kind = 'Layer' if collection == 'Layers' else 'NonSignal'
    else:
        return
    if target.kind != kind or target.parent is not board.child(collection):
        raise ReferenceError(f'{role}: target is outside this PCB {collection} collection')
    if role in ('pcb-group', 'graphic-net') and target.get('Enabled', True) is False:
        raise ReferenceError(f'{role}: target must be enabled')
    if any(link.uid != reference.uid for link in document.references.outgoing(reference.source, role=role)):
        raise ReferenceError(f'{role}: source already has a target')


def validate_field(document, node, name):
    if node.schema is graphic_records.SHAPE and name == 'Layer':
        for reference in document.references.outgoing(node, role='drawing-layer'):
            validate_reference(document, reference, reference.target)


def validate_move(document, node, parent):
    if node.schema in (graphic_records.GROUP, graphic_records.NON_SIGNAL):
        collection = 'Groups' if node.schema is graphic_records.GROUP else 'NonSignals'
        if parent is not document.one('/Board').child(collection):
            raise ReferenceError(f'{node.kind} must remain in this PCB {collection} collection')


def validate_references(document, references):
    for reference in references:
        validate_reference(document, reference, reference.target)


def validate(document):
    validate_references(document, document.references)
