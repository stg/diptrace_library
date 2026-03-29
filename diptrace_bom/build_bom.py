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

from apps.lib.dch_model import (
    detect_pattern_records_from_binary,
    extract_len16_utf16_noterm_stream,
    extract_len16_utf16_stream,
    infer_component_records_from_stream,
    read_bytes,
)


NET_PORT_RE = re.compile(r"^NetPort[0-9]{1,5}$")


def _norm_text(s: str) -> str:
    return str(s).strip(" \t")


_REF_TOKEN_RE = re.compile(r"([A-Za-z]+)|(\d+)|([^A-Za-z0-9]+)")


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


def build_bom_rows(dch_path: Path) -> list[dict[str, str]]:
    data = read_bytes(dch_path)
    lstr = extract_len16_utf16_stream(data, min_len=1, max_len=256)
    lshort = extract_len16_utf16_noterm_stream(data, min_len=1, max_len=256)
    comps = infer_component_records_from_stream(lstr, lshort, data=data)
    comps = detect_pattern_records_from_binary(data, comps)

    grouped: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for c in comps:
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
        value = _norm_text(str(c.get("value", "")))
        pattern = _norm_text(str(c.get("pattern", {}).get("name", "")) if isinstance(c.get("pattern"), dict) else "")
        grouped[(name, value, pattern)].append(ref)

    rows: list[dict[str, str]] = []
    grouped_items: list[tuple[tuple[str, str, str], list[str]]] = []
    for sig, refs in grouped.items():
        unique_refs = sorted(set(refs), key=_refdes_sort_key)
        grouped_items.append((sig, unique_refs))

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


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Build BOM CSV from one DipTrace .dch. Groups by Name+Value+Pattern and merges RefDes."
    )
    ap.add_argument("input_dch", help="Input DipTrace schematic binary (.dch)")
    ap.add_argument("output_csv", help="Output BOM CSV path")
    args = ap.parse_args()

    inp = Path(args.input_dch)
    out = Path(args.output_csv)
    if not inp.exists():
        raise SystemExit(f"input not found: {inp}")

    rows = build_bom_rows(inp)
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

    print(f"wrote={out} rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
