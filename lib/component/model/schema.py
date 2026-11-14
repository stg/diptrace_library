"""The authoritative standalone component ownership catalogue."""
from functools import lru_cache

from ...common import (drawing_records, footprint_records, group_records, library_metadata,
    local_keys, supplier_records, symbol_records, unplaced_footprint_records, user_fields, library_catalogue)
from ...common.schema_catalogue import declared_child, record_catalogue
from . import records, symbols


@lru_cache(maxsize=1)
def component_schema():
    return record_catalogue(drawing_records, footprint_records, group_records, library_metadata,
        local_keys, supplier_records, symbol_records, unplaced_footprint_records, user_fields, library_catalogue, symbols, records,
        overrides=(unplaced_footprint_records.PATTERN,), roots=(records.DOCUMENT.name,))


def definition(node):
    if node.parent is None:
        return records.DOCUMENT if not node.kind else None
    return declared_child(node.parent.schema, node.kind, component_schema())


def establish_records(root):
    for node in root.walk(include_self=True):
        if (record := definition(node)) is not None:
            node.bind_schema(record)
    return root
