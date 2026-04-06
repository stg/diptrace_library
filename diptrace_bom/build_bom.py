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

from apps.lib.dch_structural import decode_structural_components
from apps.lib.tree_query import TreeQuery


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


def _diptrace_row_sort_key(ref: str):
    r = str(ref)
    prefix_class = 0 if (r != "" and not r[0].isalnum()) else 1
    return (prefix_class, _refdes_sort_key(r))


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
        grouped_items.sort(key=lambda kv: _diptrace_row_sort_key(kv[1][0] if kv[1] else ""))
    else:
        grouped_items.sort(key=lambda kv: (kv[1][0] if kv[1] else ""))

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


def build_bom_rows_structural(dch_path: Path, *, sort_mode: str = "stable") -> tuple[list[dict[str, str]], bool]:
    tq = TreeQuery(decode_structural_components(dch_path))
    components = tq.find("Components")
    component_roots = components.find_all("Part", sort_by_offset=True) if components is not None else []
    if len(component_roots) == 0:
        raise RuntimeError("structural decode missing Components branch")

    parts: list[dict[str, object]] = []
    for rec in component_roots:
        ref = rec.text("RefDes")
        pnode = rec.find("Pattern")
        pattern_name = pnode.text("Name") if pnode is not None else ""

        parts.append(
            {
                "refdes": ref,
                "part_name": rec.text("Name"),
                "value": rec.text("Value"),
                "base_refdes": rec.text("BaseRefDes"),
                "base_name": rec.text("BaseName"),
                "part_type": 2 if NET_PORT_RE.match(ref) else 0,
                "part_name_from_base": 0,
                "pattern": {"name": pattern_name},
            }
        )

    return _group_bom_rows(parts, sort_mode=sort_mode), bool(tq.node.get("clean_eof", False))


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Build BOM CSV from one DipTrace .dch. Groups by Name+Value+Pattern and merges RefDes."
    )
    ap.add_argument("input_dch", help="Input DipTrace schematic binary (.dch)")
    ap.add_argument("output_csv", help="Output BOM CSV path")
    ap.add_argument(
        "--decoder",
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
