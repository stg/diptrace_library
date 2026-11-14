"""One authoritative schema catalogue for standalone pattern ownership."""
from functools import lru_cache

from ...common import drawing_records, footprint_records, group_records, library_metadata
from ...common import local_keys, supplier_records, user_fields, library_catalogue
from ...common.schema_catalogue import declared_child, record_catalogue
from . import records


@lru_cache(maxsize=1)
def pattern_schema():
    return record_catalogue(drawing_records, footprint_records, group_records,
        library_metadata, library_catalogue, local_keys, supplier_records, user_fields, records,
        overrides=(records.PATTERN,), roots=(records.DOCUMENT.name,))


def definition(node):
    if node.parent is None:
        return records.DOCUMENT if not node.kind else None
    return declared_child(node.parent.schema, node.kind, pattern_schema())


def establish_records(root):
    for node in root.walk(include_self=True):
        if (record := definition(node)) is not None:
            node.bind_schema(record)
    return root
