"""Board and footprint dimensions projected from current editable attachments."""
from ....common.conversion import info, warn
from ....common.model import Element
from ...model import graphic_records as model
from ..errors import PcbError
from ..output_indices import dimension_subobject
from .projection import collection, fields, non_signal_number, value


def project_dimensions(owner, *, report=None):
    """Generate ASC selectors from the model's incrementally maintained links.

    Coordinates and angles remain authored data. Export does not recalculate
    dimension layout or move its attachment targets.
    """
    board = owner.kind == 'Board'
    schema = model.COLLECTIONS['Dimensions'] if board else model.PATTERN_DIMENSIONS
    record = model.DIMENSION if board else model.PATTERN_DIMENSION
    output = Element('Dimensions')
    for dimension in collection(owner, 'Dimensions', schema, record):
        if dimension.child('UnresolvedKeys') is not None:
            raise PcbError(f'{dimension.path}: unresolved dimension extensions need an ASC mapping')
        row = output.add('Dimension')
        fields(dimension, row, exclude=('FontMono', 'Selected', 'UnresolvedNonSignal',
                                       *(('SubObject1', 'SubObject2') if board else ())))
        document = dimension._owner()
        if board:
            for side in ('1', '2'):
                name = 'SubObject'+side
                row.add(name, dimension_subobject(dimension, side))
            row.add('Group', dimension['GroupId'])
            row.add('NonSignal', non_signal_number(dimension, report=report))
            if value(dimension, 'Selected'):
                info(report, 'dimension-selection', 'asc', 'ASC omits dimension selection state', (dimension,),
                     recoverability='dimension data and attachment identities are retained')
        if document is not None and any(document.references.unresolved_slot(dimension.one(name+side))
                for side in ('1', '2') for name in ('Object', 'SubObject', 'Point')):
            warn(report, 'unresolved-dimension-attachment', 'asc', 'Dimension attachment is unavailable', (dimension,),
                 recoverability='coordinates and explicit unresolved selectors remain available')
        if value(dimension, 'FontMono'):
            warn(report, 'dimension-font-monospace', 'asc', 'ASC omits dimension monospaced-font settings', (dimension,))
    return output
