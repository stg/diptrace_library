from __future__ import annotations

# Intended use:
# Exploration/diagnostic payload builders for structural decoder output.


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


def summarize_consumed_boundaries(
    *,
    records: list[Any],
    decoded_by_index: dict[int, dict[str, Any]],
    max_samples: int = 12,
) -> dict[str, Any]:
    consumed_exact = 0
    consumed_short = 0
    consumed_overrun = 0
    consumed_missing = 0
    consumed_short_samples: list[dict[str, Any]] = []
    for r in records:
        ri = getattr(r, "index", None)
        re = getattr(r, "end", None)
        rs = getattr(r, "start", None)
        if not isinstance(ri, int) or not isinstance(re, int) or not isinstance(rs, int):
            continue
        dec = decoded_by_index.get(int(ri))
        if not isinstance(dec, dict):
            continue
        rt = str(dec.get("RecordType", ""))
        ce = dec.get("ConsumedEndOffset")
        if ce is None:
            consumed_missing += 1
            continue
        try:
            consumed_end = int(ce)
        except (TypeError, ValueError):
            consumed_missing += 1
            continue
        if consumed_end == re:
            consumed_exact += 1
        elif consumed_end < re:
            consumed_short += 1
            if len(consumed_short_samples) < int(max_samples):
                consumed_short_samples.append(
                    {
                        "index": int(ri),
                        "record_type": rt,
                        "start": int(rs),
                        "consumed_end": int(consumed_end),
                        "record_end": int(re),
                        "gap": int(re - consumed_end),
                    }
                )
        else:
            consumed_overrun += 1
    return {
        "exact": consumed_exact,
        "short": consumed_short,
        "overrun": consumed_overrun,
        "missing": consumed_missing,
        "short_samples": consumed_short_samples,
    }


def collect_tree_metrics(tree: dict[str, Any]) -> dict[str, Any]:
    nested_type_counts: dict[int, int] = {}
    nested_total = 0
    child_containment_total = 0
    child_containment_violations = 0
    part_ancestry_counts: dict[str, int] = {}
    component_container_candidates: list[dict[str, int]] = []

    def _collect_node_metrics(node: dict[str, Any], ancestry: list[tuple[str, str, int | None, int | None]]) -> None:
        nonlocal nested_total, child_containment_total, child_containment_violations
        internal = node.get("_internal", {}) if isinstance(node.get("_internal"), dict) else {}
        family = str(internal.get("family", ""))
        header = internal.get("header", {}) if isinstance(internal.get("header"), dict) else {}
        lead = header.get("Lead")
        mode = header.get("Mode")
        rec_type = str(node.get("type", ""))
        props = node.get("props", {}) if isinstance(node.get("props"), dict) else {}

        if rec_type == "Part":
            key = " > ".join(f"{nt}:{fam}:{l}:{m}" for nt, fam, l, m in ancestry)
            part_ancestry_counts[key] = part_ancestry_counts.get(key, 0) + 1

        if family == "nested":
            hb = header.get("TypeByte")
            if isinstance(hb, int):
                nested_type_counts[hb] = nested_type_counts.get(hb, 0) + 1
                nested_total += 1

        if (
            family == "token"
            and isinstance(lead, int)
            and isinstance(mode, int)
            and rec_type in ("TokenContainer", "CacheLib")
            and str(props.get("RoleCandidate", "")) == "RecordListContainer"
        ):
            internal_count = props.get("InternalRecordStartCount")
            component_container_candidates.append(
                {
                    "offset": int(internal.get("offset", -1)),
                    "length": int(internal.get("length", -1)),
                    "lead": int(lead),
                    "mode": int(mode),
                    "internal_record_starts": int(internal_count) if isinstance(internal_count, int) else -1,
                }
            )

        children = node.get("children", []) if isinstance(node.get("children"), list) else []
        po = internal.get("offset")
        pe = internal.get("end_offset")
        for ch in children:
            if not isinstance(ch, dict):
                continue
            chi = ch.get("_internal", {}) if isinstance(ch.get("_internal"), dict) else {}
            co = chi.get("offset")
            ce = chi.get("end_offset")
            if isinstance(po, int) and isinstance(pe, int) and isinstance(co, int) and isinstance(ce, int):
                child_containment_total += 1
                if co < po or ce > pe:
                    child_containment_violations += 1
            chh = chi.get("header", {}) if isinstance(chi.get("header"), dict) else {}
            _collect_node_metrics(
                ch,
                ancestry
                + [
                    (
                        "Record",
                        str(family),
                        chh.get("Lead") if isinstance(chh.get("Lead"), int) else None,
                        chh.get("Mode") if isinstance(chh.get("Mode"), int) else None,
                    )
                ],
            )

    for branch in tree.get("children", []) if isinstance(tree.get("children"), list) else []:
        if not isinstance(branch, dict):
            continue
        branch_type = str(branch.get("type", ""))
        for rec in branch.get("children", []) if isinstance(branch.get("children"), list) else []:
            if isinstance(rec, dict):
                _collect_node_metrics(rec, [("DCH", "root", None, None), ("Branch", branch_type, None, None)])

    component_container_candidates.sort(
        key=lambda x: (int(x.get("internal_record_starts", 0)), int(x.get("offset", -1))),
        reverse=True,
    )
    return {
        "NestedRecordCount": int(nested_total),
        "NestedTypeCounts": {str(k): int(v) for k, v in sorted(nested_type_counts.items())},
        "ChildContainment": {
            "total": int(child_containment_total),
            "violations": int(child_containment_violations),
        },
        "PartAncestryCounts": dict(sorted(part_ancestry_counts.items(), key=lambda kv: kv[1], reverse=True)),
        "ComponentContainerCandidatesTop": component_container_candidates[:16],
    }
