"""Discoverable immutable catalogue of the schematic record definitions."""
from functools import lru_cache
from ...common.schema_catalogue import record_catalogue


@lru_cache(maxsize=1)
def schematic_schema():
    """Return definitions keyed by record type; no design instance is required."""
    from . import (definitions, collections, simulation, membership, field_groups, auxiliary_records)
    return record_catalogue(definitions, collections, simulation, membership, field_groups, auxiliary_records,
                            overrides=(definitions.SIMULATOR, definitions.TITLE_BLOCK))
