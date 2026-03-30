from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Heuristic path intentionally disabled (kept commented for reference).
# from apps.lib.dch_heuristic import (
#     extract_len16_utf16_noterm_stream,
#     extract_len16_utf16_stream,
#     infer_component_records_from_stream,
#     read_bytes,
# )
# from apps.lib.dch_heuristic import detect_pattern_records_from_binary
from apps.lib.dch_structural import decode_structural_components
from apps.lib.component_resolver import iter_component_parts, resolve_part_pattern


NET_PORT_RE = re.compile(r"^NetPort[0-9]{1,5}$")
_REF_TOKEN_RE = re.compile(r"([A-Za-z]+)|(\d+)|([^A-Za-z0-9]+)")


def _norm_text(s: str) -> str:
    # DipTrace CSV parity canonicalization:
    # replace quote variants with space (not empty) to preserve spacing shape.
    return (
        str(s)
        .replace('"', " ")
        .replace("\u201c", " ")
        .replace("\u201d", " ")
        .strip(" \t")
    )


def _normalize_value_symbols(v: str) -> str:
    return str(v).replace("\u036b\u00a9", "kO")


def _refdes_sort_key(ref: str):
    out = []
    for a, b, c in _REF_TOKEN_RE.findall(ref):
        if b:
            out.append((1, int(b)))
        elif a:
            out.append((0, a.upper()))
        else:
            out.append((2, c))
    return out


def _group_bom_rows(comps: list[dict[str, str]], *, sort_mode: str = "stable") -> list[dict[str, str]]:
    # Collapse repeated RefDes occurrences by first-seen stream/index order.
    best_by_ref: dict[str, dict[str, str]] = {}
    for c in comps:
        ref = str(c.get("refdes", "")).strip()
        if ref == "":
            continue
        if ref not in best_by_ref:
            best_by_ref[ref] = c

    grouped: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for c in best_by_ref.values():
        ref = str(c.get("refdes", "")).strip()
        if ref == "":
            continue
        if NET_PORT_RE.match(ref):
            continue
        if int(c.get("part_type", 0)) == 2:
            continue

        name = _norm_text(str(c.get("part_name", "")))
        if int(c.get("part_name_from_base", 0)) != 0:
            name = ""
        value = _norm_text(_normalize_value_symbols(str(c.get("value", "")))
        )
        pattern = _norm_text(str(c.get("pattern", {}).get("name", "")) if isinstance(c.get("pattern"), dict) else "")
        grouped[(name, value, pattern)].append(ref)

    rows: list[dict[str, str]] = []
    grouped_items: list[tuple[tuple[str, str, str], list[str]]] = []
    for sig, refs in grouped.items():
        unique_refs = sorted(set(refs), key=_refdes_sort_key)
        grouped_items.append((sig, unique_refs))

    if sort_mode == "diptrace":
        grouped_items.sort(key=lambda kv: (kv[1][0] if kv[1] else ""))
    else:
        grouped_items.sort(key=lambda kv: _refdes_sort_key(kv[1][0] if kv[1] else ""))

    for (name, value, pattern), ref_list in grouped_items:
        rows.append(
            {
                "RefDes": ", ".join(ref_list),
                "Name": name,
                "Value": value,
                "Pattern": pattern,
            }
        )
    return rows


# Heuristic path intentionally disabled (kept commented for reference).
# def build_bom_rows_heuristic(dch_path: Path, *, sort_mode: str = "stable") -> list[dict[str, str]]:
#     data = read_bytes(dch_path)
#     lstr = extract_len16_utf16_stream(data, min_len=1, max_len=256)
#     lshort = extract_len16_utf16_noterm_stream(data, min_len=1, max_len=256)
#     comps = infer_component_records_from_stream(lstr, lshort, data=data)
#     comps = detect_pattern_records_from_binary(data, comps)
#     return _group_bom_rows(comps, sort_mode=sort_mode)


def build_bom_rows_structural(dch_path: Path, *, sort_mode: str = "stable") -> tuple[list[dict[str, str]], bool]:
    tree = decode_structural_components(dch_path)

    component_roots = iter_component_parts(tree)
    branches = tree.get("Branches", []) if isinstance(tree, dict) else []
    has_components = any(
        isinstance(b, dict) and b.get("NodeType") == "Branch" and str(b.get("Name", "")) == "Components"
        for b in branches
    ) if isinstance(branches, list) else False
    if not has_components:
        raise RuntimeError("structural decode missing Components branch")

    parts: list[dict[str, object]] = []
    for rec in component_roots:
        dec = rec.get("Decoded")
        if not isinstance(dec, dict) or dec.get("RecordType") != "Part":
            continue
        fields = dec.get("Fields", {})
        ref = str(fields.get("RefDes", "")).strip()
        pattern_name, _pattern_source = resolve_part_pattern(tree, rec)

        parts.append(
            {
                "refdes": ref,
                "part_name": str(fields.get("Name", "")),
                "value": str(fields.get("Value", "")),
                "base_refdes": str(fields.get("BaseRefDes", "")),
                "base_name": str(fields.get("BaseName", "")),
                "part_type": 2 if NET_PORT_RE.match(ref) else 0,
                "part_name_from_base": 0,
                "pattern": {"name": pattern_name},
            }
        )

    return _group_bom_rows(parts, sort_mode=sort_mode), bool(tree.get("CleanEOF", False))


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Build BOM CSV from one DipTrace .dch. Groups by Name+Value+Pattern and merges RefDes."
    )
    ap.add_argument("input_dch", help="Input DipTrace schematic binary (.dch)")
    ap.add_argument("output_csv", help="Output BOM CSV path")
    ap.add_argument(
        "--decoder",
        # Heuristic path intentionally disabled (kept commented for reference).
        # choices=["structural", "heuristic"],
        choices=["structural"],
        default="structural",
        help="Decoder base: structural (new record-framing decoder).",
    )
    ap.add_argument(
        "--sort",
        choices=["stable", "diptrace"],
        default="diptrace",
        help="BOM row sort mode: stable (natural refdes) or diptrace (raw refdes text order).",
    )
    args = ap.parse_args()

    inp = Path(args.input_dch)
    out = Path(args.output_csv)
    if not inp.exists():
        raise SystemExit(f"input not found: {inp}")

    clean_eof = True
    # Heuristic path intentionally disabled (kept commented for reference).
    # if args.decoder == "heuristic":
    #     rows = build_bom_rows_heuristic(inp, sort_mode=args.sort)
    # else:
    #     rows, clean_eof = build_bom_rows_structural(inp, sort_mode=args.sort)
    rows, clean_eof = build_bom_rows_structural(inp, sort_mode=args.sort)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["RefDes", "Name", "Value", "Pattern"],
            delimiter=";",
            quoting=csv.QUOTE_ALL,
            lineterminator="\n",
        )
        w.writeheader()
        w.writerows(rows)

    print(f"wrote={out} rows={len(rows)} decoder={args.decoder} sort={args.sort} clean_eof={int(clean_eof)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
