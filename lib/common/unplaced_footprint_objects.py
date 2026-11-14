"""Construct unplaced physical records shared by standalone library families."""
from .model import Element
from . import footprint_objects, unplaced_footprint_records as records
from . import drawing_records, footprint_records, group_records, library_metadata
from . import local_keys, supplier_records, user_fields
from .footprint_text import normalize_text_style
from .schema_catalogue import declared_child, record_catalogue
from functools import lru_cache


@lru_cache(maxsize=1)
def _physical_schema():
    return record_catalogue(drawing_records, footprint_records, group_records,
        library_metadata, local_keys, supplier_records, user_fields, records,
        overrides=(records.PATTERN,), roots=(records.PATTERN.name,))


def _complete(root):
    """Detached objects have the same typed descendants as attached objects."""
    catalogue = _physical_schema()
    for node in root.walk():
        if (record := declared_child(node.parent.schema, node.kind, catalogue)) is not None:
            node.bind_schema(record)
    return root


def new_pattern(name=''):
    pattern = footprint_objects.new_pattern(name)
    pattern.add('Sided', False)
    return _complete(pattern.bind_schema(records.PATTERN))


def new_pad(number='', name='', *, x=0, y=0):
    pad = footprint_objects.new_pad(number, name, x=x, y=y)
    for name in ('Number_New', 'Group'):
        pad.one(name).detach()
    return _complete(pad.bind_schema(records.PAD))


def new_drawing(*, kind=1):
    drawing = footprint_objects.new_pattern_drawing(kind=kind)
    for name in ('Group', 'PadId'):
        drawing.one(name).detach()
    drawing.bind_schema(records.DRAWING)
    normalize_text_style(drawing)
    return _complete(drawing)


def new_group():
    return Element('pt', True).bind_schema(records.GROUP)


def new_internal_connection():
    """Create an unassigned pair; attach it before assigning Pad1 and Pad2."""
    return Element('IntCon').bind_schema(records.PAIR)
