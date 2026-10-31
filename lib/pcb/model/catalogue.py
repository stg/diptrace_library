"""Immutable PCB record catalogue shared by reflection and documentation."""
from functools import lru_cache

from ...common.schema_catalogue import record_catalogue


@lru_cache(maxsize=1)
def pcb_schema():
    """Return the owned PCB model definitions without importing a design file."""
    from ...common import (cell_records, footprint_records, library_metadata,
                           library_records as common_library, local_keys, supplier_records, user_fields)
    from ...common import title_records as common_titles
    from . import (definitions, assembly_variants, board_records, board_rules,
                   connection_policies, drc_results, graphic_records, hierarchy_records,
                   internal_connections, length_matching, library_records, local_groups,
                   markings, membership, pad_records, pour_regions, ratlines, routing_records,
                   rule_records, settings_records, table_records, teardrops, title_records)
    return record_catalogue(
        cell_records, footprint_records, library_metadata, common_library, local_keys, supplier_records, user_fields,
        common_titles,
        definitions, assembly_variants, board_records, board_rules, connection_policies,
        drc_results, graphic_records, hierarchy_records, internal_connections, length_matching,
        library_records, local_groups, markings, membership, pad_records, pour_regions, ratlines, routing_records,
        rule_records, settings_records, table_records, teardrops, title_records,
        overrides=(library_records.PATTERN,),
        roots=(definitions.DOCUMENT.name,))
