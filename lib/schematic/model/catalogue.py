"""Discoverable immutable catalogue of the schematic record definitions."""
from functools import lru_cache
from types import MappingProxyType

from ...common.schema import Record


@lru_cache(maxsize=1)
def schematic_schema():
    """Return definitions keyed by record type; no design instance is required."""
    from . import (definitions, collections, simulation, membership, field_groups, auxiliary_records)
    records = {}
    for module in (definitions, collections, simulation, membership, field_groups, auxiliary_records):
        for name, value in vars(module).items():
            if name.startswith('_'):
                continue
            candidates = value.values() if isinstance(value, dict) else (value,)
            for definition in candidates:
                if isinstance(definition, Record):
                    records.setdefault(definition.name, definition)
    return MappingProxyType(dict(sorted(records.items())))
