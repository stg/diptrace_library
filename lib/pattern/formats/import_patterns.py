"""Standalone authoring metadata around shared footprint normalization."""
from ...common.unplaced_footprint_import import active_pad_indices, fill_defaults
from ...common.unplaced_footprint_import import normalize as normalize_footprint, finish as finish_footprints
from ..model import records
from ..model.schema import establish_records
from ...common import library_catalogue


def normalize(pattern, *, pad_indices, shape_indices, hole_indices, defaults=None):
    # An empty optional URL has no independent document meaning. Binary/ASC
    # allocate a string slot, while XML ordinarily omits the empty element.
    if (datasheet := pattern.child('Datasheet')) is not None and datasheet.values == ('',):
        datasheet.detach()
    for name, value in (defaults or {}).items():
        if name == 'Suppliers':
            pattern.append(value)
        elif name == 'Verification':
            pattern.add(name, *value)
        elif name == 'Value':
            pattern.add(name, value)
        else:
            raise ValueError('unexpected standalone pattern template field: '+name)
    return normalize_footprint(pattern, pad_indices=pad_indices, shape_indices=shape_indices,
        hole_indices=hole_indices, pattern_record=records.PATTERN, establish_records=establish_records)


def finish(document, inputs):
    return finish_footprints(document, inputs, establish_records=establish_records,
                             bind_additional=library_catalogue.bind_imported)
