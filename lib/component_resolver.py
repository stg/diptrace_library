from __future__ import annotations

# Intended use:
# Query helpers over structural DCH tree.
# Keeps cross-record selection logic outside structural decoding.

from typing import Any


def iter_component_parts(tree: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    branches = tree.get("Branches", []) if isinstance(tree, dict) else []
    if not isinstance(branches, list):
        return out
    for b in branches:
        if not (isinstance(b, dict) and b.get("NodeType") == "Branch"):
            continue
        if str(b.get("Name", "")) != "Components":
            continue
        for rec in b.get("Children", []) if isinstance(b.get("Children"), list) else []:
            if not (isinstance(rec, dict) and rec.get("NodeType") == "Record"):
                continue
            dec = rec.get("Decoded")
            if isinstance(dec, dict) and dec.get("RecordType") == "Part":
                out.append(rec)
    out.sort(key=lambda r: int(r.get("Offset", -1)))
    return out


def _extract_semantic_values(
    rec: dict[str, Any],
    *,
    key: str,
) -> list[tuple[int, int, str]]:
    out: list[tuple[int, int, str]] = []
    children = rec.get("Children")
    if not isinstance(children, list):
        return out
    for ch in children:
        if not isinstance(ch, dict):
            continue
        cdec = ch.get("Decoded")
        if not isinstance(cdec, dict):
            continue
        sems = cdec.get("Semantics")
        if not isinstance(sems, list):
            continue
        child_off = int(ch.get("Offset", 0)) if isinstance(ch.get("Offset"), int) else 0
        for s in sems:
            if not isinstance(s, dict):
                continue
            if str(s.get("key", "")) != key:
                continue
            val = str(s.get("value", "")).strip()
            if val == "":
                continue
            try:
                prio = int(s.get("priority", 0))
            except (TypeError, ValueError):
                prio = 0
            out.append((prio, child_off, val))
    return out


def extract_part_pattern_from_children(part_record: dict[str, Any]) -> str:
    vals = _extract_semantic_values(part_record, key="pattern_name")
    if not vals:
        return ""
    vals.sort(key=lambda t: (-int(t[0]), int(t[1])))
    return str(vals[0][2])


def _iter_cache_entries(tree: dict[str, Any]) -> list[dict[str, set[str]]]:
    out: list[dict[str, set[str]]] = []
    branches = tree.get("Branches", []) if isinstance(tree, dict) else []
    if not isinstance(branches, list):
        return out
    for b in branches:
        if not (isinstance(b, dict) and b.get("NodeType") == "Branch"):
            continue
        if str(b.get("Name", "")) not in ("CacheLib", "AuxTyped"):
            continue
        for rec in b.get("Children", []) if isinstance(b.get("Children"), list) else []:
            if not isinstance(rec, dict):
                continue
            dec = rec.get("Decoded")
            if not (isinstance(dec, dict) and str(dec.get("RecordType", "")) == "CacheEntry"):
                continue
            f = dec.get("Fields")
            if not isinstance(f, dict):
                continue
            names41 = set(str(x).strip() for x in f.get("Marker41Strings", []) if str(x).strip() != "")
            pats40 = set(str(x).strip() for x in f.get("Marker40Strings", []) if str(x).strip() != "")
            if names41 or pats40:
                out.append({"names41": names41, "patterns40": pats40})
    return out


def resolve_part_pattern(
    tree: dict[str, Any],
    part_record: dict[str, Any],
) -> tuple[str, str]:
    # 1) local child semantic pattern
    p = extract_part_pattern_from_children(part_record)
    if p != "":
        return p, "part_child"

    # 2) deterministic cache-link match
    dec = part_record.get("Decoded")
    if not isinstance(dec, dict):
        return "", ""
    f = dec.get("Fields")
    if not isinstance(f, dict):
        return "", ""
    ref = str(f.get("RefDes", "")).strip()
    name = str(f.get("Name", "")).strip()
    if ref == "" or name == "":
        return "", ""

    matches: list[set[str]] = []
    for ce in _iter_cache_entries(tree):
        n41 = ce.get("names41", set())
        p40 = ce.get("patterns40", set())
        if not isinstance(n41, set) or not isinstance(p40, set):
            continue
        if ref in n41 and name in n41 and len(p40) > 0:
            matches.append(p40)
    if len(matches) == 1 and len(matches[0]) == 1:
        return next(iter(matches[0])), "cache_marker"
    return "", ""

