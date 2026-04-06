from __future__ import annotations

# Intended use:
# Exploration/diagnostic payload builders for structural decoder output.
# Keeps verbose reverse-engineering metadata out of dch_structural core flow.

from typing import Any


def build_explore_record_descriptors(start_marker_hex: str) -> dict[str, Any]:
    return {
        "Part.v1": {
            "RecordType": "Part",
            "Family": "token",
            "Header": {
                "start_marker_hex": start_marker_hex,
                "text_head_offset_from_record_start": 40,
                "field_encoding": "len16be+utf16be",
            },
            "Fields": ["Name", "RefDes", "Value", "BaseRefDes", "BaseName"],
        },
        "Pattern.v1": {
            "RecordType": "Pattern",
            "Family": "subrecord",
            "Header": {
                "prelude_pattern_hex": [
                    "0f 42 [40|41|42] [00|01] 3b xx xx xx 3b xx xx xx",
                    "0f 42 [42|44] 01 3b xx xx xx 3b xx xx xx",
                ],
                "name_marker_hex": ["0f 42 40 00", "0f 42 41 00"],
                "field_encoding": "len16le+utf16le_noterm",
            },
            "Fields": ["Name"],
        },
        "TokenNamed.v1": {
            "RecordType": "TokenNamed",
            "Family": "token",
            "Header": {
                "start_pattern_hex": "x 01 01 0f 42 41 0f 42 40 00 00 00",
                "field_encoding": "len16le+utf16le",
            },
            "Fields": ["RawTypeByte", "RoleCandidate", "Name", "Meta?"],
        },
        "TokenContainer.v1": {
            "RecordType": "TokenContainer",
            "Family": "token",
            "Header": {
                "start_pattern_hex": "x 01 01 0f 42 41 0f 42 40 00 00 00 00 00 00 01 01 00 00",
                "field_encoding": "none",
            },
            "Fields": ["RawTypeByte", "InternalRecordStartCount", "RoleCandidate"],
        },
        "CacheLib.v1": {
            "RecordType": "CacheLib",
            "Family": "token",
            "Header": {
                "start_pattern_hex": "x 01 01 0f 42 41 0f 42 40 00 00 00 00 00 00 01 01 00 00",
                "field_encoding": "none",
            },
            "Fields": ["RawTypeByte", "InternalRecordStartCount", "RoleCandidate"],
        },
        "cl_Component.v1": {
            "RecordType": "cl_Component",
            "Family": "token",
            "Header": {
                "scan_markers": "0f 42 40 / 0f 42 41 + len16be_utf16be",
            },
            "Fields": ["PatternCandidates", "LinkTokens", "MarkerFields"],
        },
        "NestedRecord.v1": {
            "RecordType": "Nested",
            "Family": "nested",
            "Header": {
                "start_pattern_hex": "x 01 00 0f 42",
                "top_level_excluded_type_bytes": ["00", "0c"],
            },
            "Fields": [],
        },
    }


def build_explore_stats(
    *,
    records: list[Any],
    decoded_records: list[dict[str, Any]],
    consumed_exact: int,
    consumed_short: int,
    consumed_overrun: int,
    consumed_missing: int,
    consumed_short_samples: list[dict[str, Any]],
    nested_total: int,
    nested_type_counts: dict[Any, Any],
    nested_scan_shifted_by_consumed: int,
    enable_header_pair_collapse: bool,
    header_pair_candidates: int,
    header_pair_collapsed: int,
    header_pair_parent_decoded: int,
    header_pair_child_starts_after_consumed: int,
    header_pair_child_starts_at_consumed: int,
    child_containment_total: int,
    child_containment_violations: int,
    collapsed_indices: set[int],
    part_ancestry_counts: dict[str, int],
    component_container_candidates: list[dict[str, Any]],
    component_region_part_count: int,
    cache_region_counts: dict[str, int],
    promoted_cache_count: int,
    cache_marker_augmented_count: int,
) -> dict[str, Any]:
    return {
        "RecordCount": len(records),
        "FamilyCounts": {
            "token": sum(1 for r in records if getattr(r, "family", "") == "token"),
            "typed": sum(1 for r in records if getattr(r, "family", "") == "typed"),
            "unknown": sum(1 for r in records if getattr(r, "family", "") == "unknown"),
        },
        "DecodedRecordCount": len(decoded_records),
        "ConsumedBoundaryStats": {
            "exact": consumed_exact,
            "short": consumed_short,
            "overrun": consumed_overrun,
            "missing": consumed_missing,
            "short_samples": consumed_short_samples,
        },
        "NestedRecordCount": nested_total,
        "NestedTypeCounts": {str(k): int(v) for k, v in sorted(nested_type_counts.items())},
        "NestedScanStartShiftedByConsumedCount": int(nested_scan_shifted_by_consumed),
        "HeaderPairCollapseEvidence": {
            "enabled": bool(enable_header_pair_collapse),
            "candidates": int(header_pair_candidates),
            "collapsed": int(header_pair_collapsed),
            "parent_decoded": int(header_pair_parent_decoded),
            "child_starts_after_or_at_parent_consumed": int(header_pair_child_starts_after_consumed),
            "child_starts_exactly_at_parent_consumed": int(header_pair_child_starts_at_consumed),
        },
        "ChildContainment": {
            "total": int(child_containment_total),
            "violations": int(child_containment_violations),
        },
        "CollapsedTopLevelChildren": len(collapsed_indices),
        "PartAncestryCounts": dict(sorted(part_ancestry_counts.items(), key=lambda kv: kv[1], reverse=True)),
        "ComponentContainerCandidatesTop": component_container_candidates[:16],
        "ComponentRegionPartCount": int(component_region_part_count),
        "CacheRegionRecordTypeCounts": cache_region_counts,
        "PromotedCacheRecordCount": int(promoted_cache_count),
        "CacheMarkerAugmentedCount": int(cache_marker_augmented_count),
    }

