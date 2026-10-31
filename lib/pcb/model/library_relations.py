"""Pad identities within placed footprints and cached component definitions."""
from ...common.references import ReferenceError
from .relationships import reference_field, index_field


PIN_PAD_ROLE = 'symbol-pin-pad'
DRAWING_PAD_ROLE = 'pattern-shape-pad'
DRAWING_PAD_FIELDS = {
    'Pad': reference_field('Pad', DRAWING_PAD_ROLE),
    'PadId': index_field('PadId', DRAWING_PAD_ROLE, offset=1),
}


def validate_reference(document, reference, target):
    if reference.role == DRAWING_PAD_ROLE:
        shape = reference.source
        shapes = shape.parent
        pattern = shapes.parent if shapes is not None else None
        field = shape.schema.fields.get('Pad') if shape.schema is not None else None
        if (shape.kind != 'Shape' or field is None or field.kind != 'reference'
                or shapes is None or shapes.kind != 'Shapes'
                or pattern is None or pattern.kind != 'Pattern'
                or target.kind != 'Pad' or target.parent is not pattern.child('Pads')
                or target._owner() is not document):
            raise ReferenceError('drawing assignment requires a pad in its own footprint')
        if any(link.uid != reference.uid for link in document.references.outgoing(shape, role=DRAWING_PAD_ROLE)):
            raise ReferenceError('drawing already has a pad assignment')
        return
    if reference.role != PIN_PAD_ROLE:
        return
    part = reference.source
    definition = part.parent if part is not None else None
    slot = definition.parent if definition is not None else None
    pattern = target.parent.parent if target.parent is not None else None
    target_definition = pattern.parent if pattern is not None else None
    field = reference.indices[0].field if len(reference.indices) == 1 else None
    pin = field.parent if field is not None else None
    if (part.kind != 'Part' or definition is None or definition.kind != 'Definition'
            or part['PartType'] != 0 or pin is None or pin.kind != 'Pin'
            or pin.parent is not part.child('Pins') or field.kind != 'Number'
            or slot is None or slot.kind != 'Slot' or pattern is None or pattern.kind != 'Pattern'
            or target_definition is None or target_definition.kind != 'Definition'
            or target_definition.parent is not slot or target.kind != 'Pad'
            or target.parent is not pattern.child('Pads')
            or target._owner() is not document):
        raise ReferenceError('symbol pin assignment requires a pad in its own cached component')


def validate_references(document, references):
    for reference in references:
        validate_reference(document, reference, reference.target)
