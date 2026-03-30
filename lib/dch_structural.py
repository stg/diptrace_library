from __future__ import annotations

# Intended use:
# Structural-first DCH decoder orchestrator.
# It frames records from binary headers and dispatches to record-type decoders.
# No fallback scanning and no heuristic recovery.

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apps.lib.codec_segments import decode_pattern_children_by_descriptors
from apps.lib.codec_segments import decode_record_by_descriptor
from apps.lib.record.part import PART_RECORD_DESCRIPTOR
from apps.lib.record.pattern import PATTERN_CHILD_DESCRIPTORS
from apps.lib.record.pattern_ext import PATTERN_EXTENSION_DESCRIPTOR
from apps.lib.record.cache_entry import CACHE_ENTRY_DESCRIPTOR
from apps.lib.record.token_container import TOKEN_CONTAINER_DESCRIPTOR
from apps.lib.record.token_named import TOKEN_NAMED_DESCRIPTOR
from apps.lib.record.unknown import UNKNOWN_RECORD_DESCRIPTOR

START_MARKER = b"\x00\x01\x00\x0F\x42"
ENABLE_SYNTHETIC_RUN_GROUPING = False
ENABLE_HEADER_PAIR_COLLAPSE = True
PART_START_VARIANTS = (
    b"\x00\x01\x00\x0F\x42",  # dominant stream
    b"\x0C\x01\x00\x0F\x42",  # first-record variant observed in Laserdome
    b"\x00\x01\x01\x0F\x42",  # variant observed for top-level Part records
    b"\x0C\x01\x01\x0F\x42",  # same variant with 0x0C lead
)


@dataclass(frozen=True)
class StructuralRecord:
    index: int
    start: int
    end: int
    length: int
    lead: int
    mode: int
    family: str
    group: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "Index": self.index,
            "Offset": self.start,
            "EndOffset": self.end,
            "Length": self.length,
            "Header": {
                "Lead": self.lead,
                "Mode": self.mode,
                "MarkerHex": START_MARKER.hex(" "),
            },
            "Family": self.family,
        }


def read_bytes(path: str | Path) -> bytes:
    return Path(path).read_bytes()


def _is_strict_top_level_start(data: bytes, i: int) -> bool:
    if not (
        i + 7 < len(data)
        and data[i] in (0x00, 0x0C, 0x01)
        and data[i + 1] == 0x01
        and data[i + 2] in (0x00, 0x01)
        and data[i + 3] == 0x0F
        and data[i + 4] == 0x42
    ):
        return False
    mode = data[i + 6]
    next_b = data[i + 7]
    # Observed invariant across corpus:
    #  - mode 0x0F records continue with 0x42
    #  - mode 0x00/0x01 records continue with token lead bytes
    if mode == 0x0F:
        return next_b == 0x42
    if mode == 0x01:
        return next_b == 0x0F
    if mode == 0x00:
        return next_b in (0x0F, 0x01)
    return False


def _is_generic_record_start(data: bytes, i: int, *, allow_top_lead: bool) -> bool:
    if not (
        i + 7 < len(data)
        and data[i + 1] == 0x01
        and data[i + 2] in (0x00, 0x01)
        and data[i + 3] == 0x0F
        and data[i + 4] == 0x42
    ):
        return False
    x = data[i]
    if allow_top_lead:
        if x not in (0x00, 0x0C, 0x01):
            return False
    else:
        if x in (0x00, 0x0C):
            return False
    mode = data[i + 6]
    next_b = data[i + 7]
    if mode == 0x0F:
        return next_b == 0x42
    if mode == 0x01:
        return next_b == 0x0F
    if mode == 0x00:
        return next_b in (0x0F, 0x01)
    return False


def _find_next_strict_top_level_start(data: bytes, start: int) -> int:
    i = max(0, start)
    limit = len(data) - 6
    while i < limit:
        if _is_strict_top_level_start(data, i):
            return i
        i += 1
    return -1


def _find_first_top_level_start(data: bytes) -> int:
    first_strict = _find_next_strict_top_level_start(data, 0)
    if first_strict < 0:
        return -1

    # Leading prelude record: some files begin with one top-level token record
    # encoded as x 01 yy 0F 42 (x != 00/0C) before the strict stream.
    i = 0
    while i + 6 < first_strict:
        if (
            data[i] not in (0x00, 0x0C)
            and data[i + 1] == 0x01
            and data[i + 2] in (0x00, 0x01)
            and data[i + 3] == 0x0F
            and data[i + 4] == 0x42
            and data[i + 6] == 0x0F
        ):
            return i
        i += 1
    return first_strict


def _find_internal_record_starts(data: bytes, start: int, end: int) -> list[tuple[int, int]]:
    # General nested candidate:
    #   x 01 yy 0F 42, where x != {00,0C}
    out: list[tuple[int, int]] = []
    p = max(start + 1, 0)
    lim = min(end, len(data))
    while p + 6 < lim:
        if _is_generic_record_start(data, p, allow_top_lead=False):
            out.append((p, data[p]))
        p += 1
    return out


def classify_family(mode: int) -> str:
    if mode == 0x0F:
        return "token"
    if mode in (0x00, 0x01):
        return "typed"
    return "unknown"


def decode_structural_records(data: bytes) -> list[StructuralRecord]:
    out: list[StructuralRecord] = []
    s = _find_first_top_level_start(data)
    i = 0
    while s >= 0:
        n = _find_next_strict_top_level_start(data, s + 1)
        e = n if n >= 0 else len(data)
        lead = data[s + 5] if s + 5 < len(data) else -1
        mode = data[s + 6] if s + 6 < len(data) else -1
        out.append(
            StructuralRecord(
                index=i,
                start=s,
                end=e,
                length=e - s,
                lead=lead,
                mode=mode,
                family=classify_family(mode),
                group=0,
            )
        )
        if n < 0:
            break
        s = n
        i += 1
    return out


def _decode_record_payloads(data: bytes, records: list[StructuralRecord]) -> list[dict[str, Any]]:
    decoded: list[dict[str, Any]] = []
    for r in records:
        dec = _decode_one_record(data, r)
        if dec is not None:
            decoded.append(dec)
    return decoded


def _decode_one_record(data: bytes, r: StructuralRecord) -> dict[str, Any] | None:
    # Descriptor-driven decoder selection.
    def _try_descriptors(descs: list[dict[str, Any]]) -> dict[str, Any] | None:
        for d in descs:
            dec = decode_record_by_descriptor(
                data,
                record_index=r.index,
                record_start=r.start,
                record_end=r.end,
                descriptor=d,
            )
            if dec is not None:
                return dec
        return None

    if r.family in ("token", "nested"):
        dec = _try_descriptors(
            [
                TOKEN_NAMED_DESCRIPTOR,
                TOKEN_CONTAINER_DESCRIPTOR,
                PART_RECORD_DESCRIPTOR,
                CACHE_ENTRY_DESCRIPTOR,
            ]
        )
        if dec is not None:
            return dec
        return decode_record_by_descriptor(
            data,
            record_index=r.index,
            record_start=r.start,
            record_end=r.end,
            descriptor=UNKNOWN_RECORD_DESCRIPTOR,
        )
    if r.family in ("typed", "nested") and r.mode == 1:
        dec = _try_descriptors([PATTERN_EXTENSION_DESCRIPTOR, CACHE_ENTRY_DESCRIPTOR])
        if dec is not None:
            return dec
        return decode_record_by_descriptor(
            data,
            record_index=r.index,
            record_start=r.start,
            record_end=r.end,
            descriptor=UNKNOWN_RECORD_DESCRIPTOR,
        )
    return decode_record_by_descriptor(
        data,
        record_index=r.index,
        record_start=r.start,
        record_end=r.end,
        descriptor=UNKNOWN_RECORD_DESCRIPTOR,
    )


def decode_structural_components(path: str | Path) -> dict[str, Any]:
    data = read_bytes(path)
    records = decode_structural_records(data)
    decoded_records = _decode_record_payloads(data, records)
    decoded_by_index: dict[int, dict[str, Any]] = {}
    for d in decoded_records:
        try:
            decoded_by_index[int(d.get("RecordIndex", -1))] = d
        except (TypeError, ValueError):
            continue
    decoded_any_cache: dict[tuple[int, int, int, int, str], dict[str, Any] | None] = {}

    def _is_known_decoded(dec: dict[str, Any] | None) -> bool:
        return isinstance(dec, dict) and str(dec.get("RecordType", "")) != "Unknown"

    def _decode_cached(r: StructuralRecord) -> dict[str, Any] | None:
        k = (int(r.start), int(r.end), int(r.mode), int(r.lead), str(r.family))
        if k in decoded_any_cache:
            return decoded_any_cache[k]
        dec = _decode_one_record(data, r)
        decoded_any_cache[k] = dec
        return dec

    # Structural depth rules from header transitions only.
    # Rule A: token(b2=0) -> typed(mode=1) immediate follower is a child.
    # Rule B: token(b2=1) -> typed(mode=0) immediate follower is a child.
    # These are header-class transitions, not record-type checks.
    collapsed_children_by_parent_index: dict[int, list[StructuralRecord]] = {}
    collapsed_child_indices: set[int] = set()
    header_pair_relation_by_child_index: dict[int, dict[str, int]] = {}
    header_pair_candidates = 0
    header_pair_collapsed = 0
    header_pair_parent_decoded = 0
    header_pair_child_starts_after_consumed = 0
    header_pair_child_starts_at_consumed = 0
    if ENABLE_HEADER_PAIR_COLLAPSE:
        for i in range(0, len(records) - 1):
            r = records[i]
            n = records[i + 1]
            if n.index in collapsed_child_indices:
                continue
            rb2 = data[r.start + 2] if r.start + 2 < len(data) else -1
            attach = r.mode == 0x0F and (
                (rb2 == 0x00 and n.mode == 0x01) or (rb2 == 0x01 and n.mode == 0x00)
            )
            if attach:
                header_pair_candidates += 1
                pdec = decoded_by_index.get(r.index)
                if isinstance(pdec, dict):
                    header_pair_parent_decoded += 1
                    ce = pdec.get("ConsumedEndOffset")
                    if isinstance(ce, int):
                        if n.start >= ce:
                            header_pair_child_starts_after_consumed += 1
                        if n.start == ce:
                            header_pair_child_starts_at_consumed += 1
            if not attach:
                continue
            collapsed_children_by_parent_index.setdefault(r.index, []).append(n)
            collapsed_child_indices.add(n.index)
            header_pair_collapsed += 1
            rel: dict[str, int] = {
                "parent_index": int(r.index),
                "parent_start": int(r.start),
                "parent_end": int(r.end),
                "child_start": int(n.start),
                "child_end": int(n.end),
            }
            pdec2 = decoded_by_index.get(r.index)
            if isinstance(pdec2, dict):
                ce2 = pdec2.get("ConsumedEndOffset")
                if isinstance(ce2, int):
                    rel["parent_consumed_end"] = int(ce2)
                    rel["gap_from_parent_consumed"] = int(n.start - ce2)
            header_pair_relation_by_child_index[n.index] = rel

    # Stage-2 section collapse (optional synthetic grouping):
    # Consecutive undecoded token records with header class (lead=0x41, mode=0x0F)
    # grouped under first record in run as sibling children.
    section_group_children_by_parent_index: dict[int, list[StructuralRecord]] = {}
    section_group_collapsed_indices: set[int] = set()
    if ENABLE_SYNTHETIC_RUN_GROUPING:
        visible_after_stage1 = [r for r in records if r.index not in collapsed_child_indices]
        i = 0
        while i < len(visible_after_stage1):
            r = visible_after_stage1[i]
            dr = decoded_by_index.get(r.index)
            if not (r.mode == 0x0F and r.lead == 0x41 and not _is_known_decoded(dr)):
                i += 1
                continue
            j = i + 1
            group_children: list[StructuralRecord] = []
            while j < len(visible_after_stage1):
                n = visible_after_stage1[j]
                dn = decoded_by_index.get(n.index)
                if not (n.mode == 0x0F and n.lead == 0x41 and not _is_known_decoded(dn)):
                    break
                group_children.append(n)
                j += 1
            if group_children:
                section_group_children_by_parent_index[r.index] = group_children
                for c in group_children:
                    section_group_collapsed_indices.add(c.index)
            i = j

    # Stage-3 top-level run grouping (optional synthetic grouping):
    # collapse consecutive visible undecoded token records (mode=0x0F, b2=1) under first.
    run_group_children_by_parent_index: dict[int, list[StructuralRecord]] = {}
    run_group_collapsed_indices: set[int] = set()
    if ENABLE_SYNTHETIC_RUN_GROUPING:
        visible_after_stage2 = [
            r for r in records if r.index not in (collapsed_child_indices | section_group_collapsed_indices)
        ]
        i = 0
        while i < len(visible_after_stage2):
            r = visible_after_stage2[i]
            rb2 = data[r.start + 2] if r.start + 2 < len(data) else -1
            dr = decoded_by_index.get(r.index)
            if not (r.mode == 0x0F and rb2 == 0x01 and not _is_known_decoded(dr)):
                i += 1
                continue
            j = i + 1
            children: list[StructuralRecord] = []
            while j < len(visible_after_stage2):
                n = visible_after_stage2[j]
                nb2 = data[n.start + 2] if n.start + 2 < len(data) else -1
                dn = decoded_by_index.get(n.index)
                if not (n.mode == 0x0F and nb2 == 0x01 and not _is_known_decoded(dn)):
                    break
                children.append(n)
                j += 1
            if children:
                run_group_children_by_parent_index[r.index] = children
                for c in children:
                    run_group_collapsed_indices.add(c.index)
            i = j

    # Structural tree: root -> contiguous mode-runs -> record nodes.
    # Nested records are parsed recursively by the same structural header rule.
    def _should_attach_child_by_header(parent: dict[str, Any], child: dict[str, Any]) -> bool:
        try:
            po = int(parent.get("Offset", -1))
            pmode = int(parent.get("Header", {}).get("Mode", -1))
            cmode = int(child.get("Header", {}).get("Mode", -1))
        except (TypeError, ValueError):
            return False
        if po < 0 or po + 2 >= len(data):
            return False
        pb2 = data[po + 2]
        return pmode == 0x0F and ((pb2 == 0x00 and cmode == 0x01) or (pb2 == 0x01 and cmode == 0x00))

    def _collapse_children_by_header(children: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not children:
            return children
        out: list[dict[str, Any]] = []
        i = 0
        while i < len(children):
            p = children[i]
            if i + 1 < len(children):
                c = children[i + 1]
                pf = str(p.get("Family", ""))
                cf = str(c.get("Family", ""))
                structural_ok = pf not in ("subrecord", "extension") and cf not in ("subrecord", "extension")
                if structural_ok and _should_attach_child_by_header(p, c):
                    p_children = p.get("Children")
                    if not isinstance(p_children, list):
                        p["Children"] = [c]
                    else:
                        p_children.append(c)
                    out.append(p)
                    i += 2
                    continue
            out.append(p)
            i += 1
        return out

    nested_scan_shifted_by_consumed = 0

    def _build_record_node(r: StructuralRecord, depth: int = 0, max_depth: int = 6) -> dict[str, Any]:
        nonlocal nested_scan_shifted_by_consumed
        dec = decoded_by_index.get(r.index) if r.family != "nested" else _decode_cached(r)
        child_nodes: list[dict[str, Any]] = []
        parse_generic_nested = not (isinstance(dec, dict) and dec.get("RecordType") == "Part")
        if depth < max_depth and parse_generic_nested:
            nested_scan_start = r.start
            if isinstance(dec, dict):
                ce = dec.get("ConsumedEndOffset")
                if isinstance(ce, int) and r.start <= ce <= r.end:
                    if ce > nested_scan_start:
                        nested_scan_start = ce
                        nested_scan_shifted_by_consumed += 1
            nested = _find_internal_record_starts(data, nested_scan_start, r.end)
            for i, (cs, x) in enumerate(nested):
                ce = nested[i + 1][0] if i + 1 < len(nested) else r.end
                clead = data[cs + 5] if cs + 5 < len(data) else -1
                cmode = data[cs + 6] if cs + 6 < len(data) else -1
                nr = StructuralRecord(
                    index=i,
                    start=cs,
                    end=ce,
                    length=ce - cs,
                    lead=clead,
                    mode=cmode,
                    family="nested",
                )
                nnode = _build_record_node(nr, depth=depth + 1, max_depth=max_depth)
                # Preserve nested-local header type byte.
                nnode["Header"] = {
                    "TypeByte": x,
                    "Lead": clead,
                    "Mode": cmode,
                }
                child_nodes.append(nnode)

        if isinstance(dec, dict) and dec.get("RecordType") == "Part":
            children = decode_pattern_children_by_descriptors(
                data,
                parent_record_index=r.index,
                parent_record_start=r.start,
                parent_record_end=int(r.end),
                descriptors=PATTERN_CHILD_DESCRIPTORS,
            )
            child_nodes.extend(
                [
                    {
                        "NodeType": "Record",
                        "Index": len(child_nodes) + int(c.get("RecordIndex", 0)),
                        "Offset": int(c.get("Offset", -1)),
                        "EndOffset": int(c.get("EndOffset", -1)),
                        "Length": int(c.get("Length", -1)),
                        "Header": {"Lead": -1, "Mode": -1},
                        "Family": "subrecord",
                        "Decoded": c,
                        "Children": [],
                    }
                    for c in children
                ]
            )

        for cr in collapsed_children_by_parent_index.get(r.index, []):
            ch_node = _build_record_node(cr, depth=depth + 1, max_depth=max_depth)
            rel = header_pair_relation_by_child_index.get(cr.index)
            if isinstance(rel, dict):
                ch_node["AttachedByHeaderPair"] = rel
            child_nodes.append(ch_node)
        for cr in section_group_children_by_parent_index.get(r.index, []):
            child_nodes.append(_build_record_node(cr, depth=depth + 1, max_depth=max_depth))
        for cr in run_group_children_by_parent_index.get(r.index, []):
            child_nodes.append(_build_record_node(cr, depth=depth + 1, max_depth=max_depth))

        child_nodes.sort(key=lambda n: int(n.get("Offset", 0)))
        child_nodes = _collapse_children_by_header(child_nodes)

        return {
            "NodeType": "Record",
            "Index": r.index,
            "Offset": r.start,
            "EndOffset": r.end,
            "Length": r.length,
            "Header": {"Lead": r.lead, "Mode": r.mode},
            "Family": r.family,
            "Decoded": dec,
            "Children": child_nodes,
        }

    collapsed_indices = collapsed_child_indices | section_group_collapsed_indices | run_group_collapsed_indices
    visible_records = [r for r in records if r.index not in collapsed_indices]
    run_nodes: list[dict[str, Any]] = []
    if visible_records:
        run_start = 0
        cur_mode = visible_records[0].mode
        for i in range(1, len(visible_records)):
            if visible_records[i].mode != cur_mode:
                seg = visible_records[run_start:i]
                seg_children = [_build_record_node(r, depth=0) for r in seg]
                type_counts: dict[str, int] = {}
                part_positions: list[int] = []
                nonpart_positions: list[int] = []
                for j, r in enumerate(seg):
                    decj = decoded_by_index.get(r.index)
                    rtj = str(decj.get("RecordType", "None")) if isinstance(decj, dict) else "None"
                    type_counts[rtj] = type_counts.get(rtj, 0) + 1
                    if rtj == "Part":
                        part_positions.append(j)
                    else:
                        nonpart_positions.append(j)
                branch_hint = "non_token_run"
                cache_tail_start_offset: int | None = None
                if int(cur_mode) == 0x0F:
                    part_count = int(type_counts.get("Part", 0))
                    nonpart_count = int(len(seg) - part_count)
                    if part_count == 0 and nonpart_count > 0:
                        branch_hint = "cache_run"
                    elif part_count > 0 and nonpart_count == 0:
                        branch_hint = "components_only"
                    elif part_count > 0 and nonpart_count > 0:
                        first_nonpart = min(nonpart_positions) if nonpart_positions else -1
                        part_after_nonpart = sum(1 for p in part_positions if p > first_nonpart) if first_nonpart >= 0 else 0
                        if part_after_nonpart == 0 and first_nonpart >= 0:
                            branch_hint = "components_then_cache_tail"
                            if 0 <= first_nonpart < len(seg):
                                cache_tail_start_offset = int(seg[first_nonpart].start)
                        else:
                            branch_hint = "components_mixed"
                            if part_positions:
                                last_part = max(part_positions)
                                if 0 <= last_part + 1 < len(seg):
                                    cache_tail_start_offset = int(seg[last_part + 1].start)
                run_nodes.append(
                    {
                        "NodeType": "ModeRun",
                        "Mode": int(cur_mode),
                        "Family": seg[0].family,
                        "StartIndex": seg[0].index,
                        "EndIndex": seg[-1].index,
                        "Offset": seg[0].start,
                        "EndOffset": seg[-1].end,
                        "Count": len(seg),
                        "Children": seg_children,
                        "RunRecordTypeCounts": dict(sorted(type_counts.items())),
                        "BranchHint": branch_hint,
                        "CacheTailStartOffset": cache_tail_start_offset,
                    }
                )
                run_start = i
                cur_mode = visible_records[i].mode
        seg = visible_records[run_start:]
        seg_children = [_build_record_node(r, depth=0) for r in seg]
        type_counts: dict[str, int] = {}
        part_positions: list[int] = []
        nonpart_positions: list[int] = []
        for j, r in enumerate(seg):
            decj = decoded_by_index.get(r.index)
            rtj = str(decj.get("RecordType", "None")) if isinstance(decj, dict) else "None"
            type_counts[rtj] = type_counts.get(rtj, 0) + 1
            if rtj == "Part":
                part_positions.append(j)
            else:
                nonpart_positions.append(j)
        branch_hint = "non_token_run"
        cache_tail_start_offset: int | None = None
        if int(cur_mode) == 0x0F:
            part_count = int(type_counts.get("Part", 0))
            nonpart_count = int(len(seg) - part_count)
            if part_count == 0 and nonpart_count > 0:
                branch_hint = "cache_run"
            elif part_count > 0 and nonpart_count == 0:
                branch_hint = "components_only"
            elif part_count > 0 and nonpart_count > 0:
                first_nonpart = min(nonpart_positions) if nonpart_positions else -1
                part_after_nonpart = sum(1 for p in part_positions if p > first_nonpart) if first_nonpart >= 0 else 0
                if part_after_nonpart == 0 and first_nonpart >= 0:
                    branch_hint = "components_then_cache_tail"
                    if 0 <= first_nonpart < len(seg):
                        cache_tail_start_offset = int(seg[first_nonpart].start)
                else:
                    branch_hint = "components_mixed"
                    if part_positions:
                        last_part = max(part_positions)
                        if 0 <= last_part + 1 < len(seg):
                            cache_tail_start_offset = int(seg[last_part + 1].start)
        run_nodes.append(
            {
                "NodeType": "ModeRun",
                "Mode": int(cur_mode),
                "Family": seg[0].family,
                "StartIndex": seg[0].index,
                "EndIndex": seg[-1].index,
                "Offset": seg[0].start,
                "EndOffset": seg[-1].end,
                "Count": len(seg),
                "Children": seg_children,
                "RunRecordTypeCounts": dict(sorted(type_counts.items())),
                "BranchHint": branch_hint,
                "CacheTailStartOffset": cache_tail_start_offset,
            }
        )

    nested_type_counts: dict[int, int] = {}
    nested_total = 0
    child_containment_total = 0
    child_containment_violations = 0

    def _walk(n: dict[str, Any]) -> list[dict[str, Any]]:
        outn = [n]
        for c in n.get("Children", []) if isinstance(n, dict) else []:
            if isinstance(c, dict):
                outn.extend(_walk(c))
        return outn

    for run in run_nodes:
        for rec in run.get("Children", []):
            if not isinstance(rec, dict):
                continue
            for ch in _walk(rec):
                if ch.get("Family") != "nested":
                    continue
                hb = ch.get("Header", {}).get("TypeByte")
                if isinstance(hb, int):
                    nested_type_counts[hb] = nested_type_counts.get(hb, 0) + 1
                    nested_total += 1

    def _count_containment(node: dict[str, Any]) -> None:
        nonlocal child_containment_total, child_containment_violations
        po = node.get("Offset")
        pe = node.get("EndOffset")
        if isinstance(po, int) and isinstance(pe, int):
            for c in node.get("Children", []) if isinstance(node.get("Children"), list) else []:
                if not isinstance(c, dict):
                    continue
                co = c.get("Offset")
                ce = c.get("EndOffset")
                if isinstance(co, int) and isinstance(ce, int):
                    child_containment_total += 1
                    if co < po or ce > pe:
                        child_containment_violations += 1
                _count_containment(c)

    for run in run_nodes:
        for rec in run.get("Children", []) if isinstance(run.get("Children"), list) else []:
            if isinstance(rec, dict):
                _count_containment(rec)

    consumed_exact = 0
    consumed_short = 0
    consumed_overrun = 0
    consumed_missing = 0
    consumed_short_samples: list[dict[str, int | str]] = []
    for r in records:
        dec = decoded_by_index.get(r.index)
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
        if consumed_end == r.end:
            consumed_exact += 1
        elif consumed_end < r.end:
            consumed_short += 1
            if len(consumed_short_samples) < 12:
                consumed_short_samples.append(
                    {
                        "index": int(r.index),
                        "record_type": rt,
                        "start": int(r.start),
                        "consumed_end": int(consumed_end),
                        "record_end": int(r.end),
                        "gap": int(r.end - consumed_end),
                    }
                )
        else:
            consumed_overrun += 1

    part_ancestry_counts: dict[str, int] = {}
    component_container_candidates: list[dict[str, int]] = []

    def _walk_with_ancestry(node: dict[str, Any], ancestry: list[tuple[str, str, int | None, int | None]]) -> None:
        dec = node.get("Decoded")
        if isinstance(dec, dict) and dec.get("RecordType") == "Part":
            key = " > ".join(
                f"{nt}:{fam}:{lead}:{mode}" for nt, fam, lead, mode in ancestry
            )
            part_ancestry_counts[key] = part_ancestry_counts.get(key, 0) + 1

        if node.get("NodeType") == "Record":
            hdr = node.get("Header", {}) if isinstance(node.get("Header"), dict) else {}
            lead = hdr.get("Lead")
            mode = hdr.get("Mode")
            if (
                node.get("Family") == "token"
                and isinstance(lead, int)
                and isinstance(mode, int)
                and isinstance(dec, dict)
                and dec.get("RecordType") == "TokenContainer"
            ):
                f = dec.get("Fields", {}) if isinstance(dec.get("Fields"), dict) else {}
                role = str(f.get("RoleCandidate", ""))
                internal = f.get("InternalRecordStartCount")
                if role == "RecordListContainer":
                    component_container_candidates.append(
                        {
                            "offset": int(node.get("Offset", -1)),
                            "length": int(node.get("Length", -1)),
                            "lead": int(lead),
                            "mode": int(mode),
                            "internal_record_starts": int(internal) if isinstance(internal, int) else -1,
                        }
                    )

        for ch in node.get("Children", []) if isinstance(node.get("Children"), list) else []:
            if not isinstance(ch, dict):
                continue
            ch_hdr = ch.get("Header", {}) if isinstance(ch.get("Header"), dict) else {}
            _walk_with_ancestry(
                ch,
                ancestry
                + [
                    (
                        str(node.get("NodeType", "")),
                        str(node.get("Family", "")),
                        ch_hdr.get("Lead") if isinstance(ch_hdr.get("Lead"), int) else None,
                        ch_hdr.get("Mode") if isinstance(ch_hdr.get("Mode"), int) else None,
                    )
                ],
            )

    for run in run_nodes:
        if not isinstance(run, dict):
            continue
        for rec in run.get("Children", []) if isinstance(run.get("Children"), list) else []:
            if not isinstance(rec, dict):
                continue
            run_mode = int(run.get("Mode", -1))
            _walk_with_ancestry(
                rec,
                [("DCH", "root", None, None), ("ModeRun", str(run.get("Family", "")), None, run_mode)],
            )

    component_container_candidates.sort(
        key=lambda x: (int(x.get("internal_record_starts", 0)), int(x.get("offset", -1))),
        reverse=True,
    )

    cache_region_counts: dict[str, int] = {
        "runs": 0,
        "records": 0,
        "Part": 0,
        "TokenNamed": 0,
        "TokenContainer": 0,
        "Unknown": 0,
    }
    component_region_part_count = 0
    component_branch_records: list[dict[str, Any]] = []
    cache_branch_records: list[dict[str, Any]] = []
    for run in run_nodes:
        if not isinstance(run, dict):
            continue
        mode = int(run.get("Mode", -1)) if isinstance(run.get("Mode"), int) else -1
        if mode != 0x0F:
            continue
        hint = str(run.get("BranchHint", ""))
        cache_tail_start = run.get("CacheTailStartOffset")
        cache_tail_start_i = int(cache_tail_start) if isinstance(cache_tail_start, int) else None
        children = run.get("Children", []) if isinstance(run.get("Children"), list) else []
        if hint == "cache_run":
            cache_region_counts["runs"] += 1
            for rec in children:
                if not isinstance(rec, dict):
                    continue
                cache_branch_records.append(rec)
                dec = rec.get("Decoded")
                rt = str(dec.get("RecordType", "Unknown")) if isinstance(dec, dict) else "Unknown"
                cache_region_counts["records"] += 1
                cache_region_counts[rt] = int(cache_region_counts.get(rt, 0)) + 1
            continue

        for rec in children:
            if not isinstance(rec, dict):
                continue
            rec_off = int(rec.get("Offset", -1)) if isinstance(rec.get("Offset"), int) else -1
            dec = rec.get("Decoded")
            rt = str(dec.get("RecordType", "Unknown")) if isinstance(dec, dict) else "Unknown"
            in_cache_tail = cache_tail_start_i is not None and rec_off >= cache_tail_start_i
            if in_cache_tail:
                cache_branch_records.append(rec)
                cache_region_counts["records"] += 1
                cache_region_counts[rt] = int(cache_region_counts.get(rt, 0)) + 1
            else:
                component_branch_records.append(rec)
                if rt == "Part":
                    component_region_part_count += 1

    aux_typed_records: list[dict[str, Any]] = []
    for run in run_nodes:
        if not isinstance(run, dict):
            continue
        mode = int(run.get("Mode", -1)) if isinstance(run.get("Mode"), int) else -1
        if mode in (0x0F,):
            continue
        for rec in run.get("Children", []) if isinstance(run.get("Children"), list) else []:
            if isinstance(rec, dict) and rec.get("NodeType") == "Record":
                aux_typed_records.append(rec)

    branch_nodes: list[dict[str, Any]] = []
    if component_branch_records:
        branch_nodes.append(
            {
                "NodeType": "Branch",
                "Name": "Components",
                "Children": component_branch_records,
            }
        )
    if cache_branch_records:
        branch_nodes.append(
            {
                "NodeType": "Branch",
                "Name": "CacheLib",
                "Children": cache_branch_records,
            }
        )
    if aux_typed_records:
        branch_nodes.append(
            {
                "NodeType": "Branch",
                "Name": "AuxTyped",
                "Children": aux_typed_records,
            }
        )

    return {
        "NodeType": "DCH",
        "Source": str(path),
        "Offset": 0,
        "EndOffset": len(data),
        "RecordStartMarkerHex": START_MARKER.hex(" "),
        "RecordDescriptors": {
            "Part.v1": {
                "RecordType": "Part",
                "Family": "token",
                "Header": {
                    "start_marker_hex": START_MARKER.hex(" "),
                    "text_head_offset_from_record_start": 40,
                    "field_encoding": "len16be+utf16be",
                },
                "Fields": ["Name", "RefDes", "Value", "BaseRefDes", "BaseName"],
            },
            "PatternChild.v2": {
                "RecordType": "Pattern",
                "Family": "subrecord",
                "Header": {
                    "prelude_pattern_hex": "0f 42 [40|41|42] [00|01] 3b xx xx xx 3b xx xx xx",
                    "name_marker_hex": "0f 42 40 00",
                    "field_encoding": "len16le+utf16le_noterm",
                },
                "Fields": ["Name"],
            },
            "PatternChild.v3": {
                "RecordType": "Pattern",
                "Family": "subrecord",
                "Header": {
                    "prelude_pattern_hex": "0f 42 [42|44] 01 3b xx xx xx 3b xx xx xx",
                    "name_marker_hex": "0f 42 41 00",
                    "field_encoding": "len16le+utf16le_noterm",
                },
                "Fields": ["Name"],
            },
            "PatternExtension.v1": {
                "RecordType": "PatternExtension",
                "Family": "typed",
                "Header": {
                    "prelude_pattern_hex": "0f 42 [40|41|42] [00|01] 3b xx xx xx 3b xx xx xx",
                    "name_marker_hex": "0f 42 40 00",
                    "field_encoding": "len16le+utf16le_noterm",
                    "record_mode": 1,
                },
                "Fields": ["PrimaryName", "Names"],
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
            "NestedRecord.v1": {
                "RecordType": "Nested",
                "Family": "nested",
                "Header": {
                    "start_pattern_hex": "x 01 00 0f 42",
                    "top_level_excluded_type_bytes": ["00", "0c"],
                },
                "Fields": [],
            }
        },
        "Stats": {
            "RecordCount": len(records),
            "FamilyCounts": {
                "token": sum(1 for r in records if r.family == "token"),
                "typed": sum(1 for r in records if r.family == "typed"),
                "unknown": sum(1 for r in records if r.family == "unknown"),
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
                "enabled": bool(ENABLE_HEADER_PAIR_COLLAPSE),
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
        },
        "CleanEOF": True,
        "Children": run_nodes,
        "Branches": branch_nodes,
    }
