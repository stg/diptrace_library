"""Custom-layer choices retain identity even while another layer family is used."""
from ...common.references import ReferenceError
from .relationships import optional_reference_fields


ROLE = 'non-signal-layer'
SELECTION_FIELDS = optional_reference_fields('NonSignalLayer', 'NonSignal', ROLE)


def validate_reference(document, reference, target):
    if reference.role != ROLE:
        return
    board, source = document.one('/Board'), reference.source
    collection = {'Table': 'Tables', 'Dimension': 'Dimensions'}.get(source.kind)
    if (collection is None or source.parent is not board.child(collection)
            or source.schema is None or source.schema.fields.get('NonSignalLayer') is not SELECTION_FIELDS['NonSignalLayer']
            or target.kind != 'NonSignal' or target.parent is not board.child('NonSignals')
            or target._owner() is not document):
        raise ReferenceError('non-signal selection requires a custom layer in its own PCB')
    if any(link.uid != reference.uid for link in document.references.outgoing(source, role=ROLE)):
        raise ReferenceError('non-signal selection already has a target')


def validate_references(document, references):
    for reference in references:
        validate_reference(document, reference, reference.target)
