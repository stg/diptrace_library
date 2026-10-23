from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.deprecated.pre_shared_model.lib.heuristic.decoder import decode_model as decode_model_heuristic
from apps.deprecated.pre_shared_model.lib.structural.decoder import decode_structural_components, encode_structural_tree
from apps.deprecated.pre_shared_model.lib.tree_query import TreeQuery

_NUM_SPLIT_RE = re.compile(r"(\d+)")

def natural_key(ref: str):
    return [
        (1, int(p)) if p.isdigit() else (0, p.upper())
        for p in _NUM_SPLIT_RE.split(str(ref))
        if p
    ]

def group_bom(comps: list[dict[str, object]]) -> list[dict[str, str]]:
    # Keep first occurrence per RefDes (stable stream order).
    seen_refdes: set[str] = set()
    grouped: dict[tuple[str, str, str], set[str]] = defaultdict(set)

    for c in comps:
        ref = str(c.get("refdes", "")).strip()
        if not ref or ref in seen_refdes: continue
        seen_refdes.add(ref)
        if int(c.get("part_type", 0)) == 2: continue
        grouped[c.get("name", ""), c.get("value", ""), c.get("pattern", "")].add(ref)

    grouped_items: list[tuple[tuple[str, str, str], list[str]]] = [
        (sig, sorted(refs, key=natural_key)) for sig, refs in grouped.items()
    ]

    grouped_items.sort(key=lambda kv: natural_key(kv[1][0]))

    return [
        {
            "RefDes": ", ".join(ref_list),
            "Name": name,
            "Value": value,
            "Pattern": pattern,
        }
        for (name, value, pattern), ref_list in grouped_items
    ]

def _parts_from_tree_model(tree: dict[str, object]) -> tuple[list[dict[str, object]], bool]:
    tq = TreeQuery(tree)
    components = tq.find("Components")
    component_roots = components.find_all("Part", sort_by_offset=True) if components is not None else []
    if not component_roots:
        raise RuntimeError("decode missing Components branch")

    parts: list[dict[str, object]] = []

    for rec in component_roots:
        ref = rec.text("RefDes")
        pnode = rec.find("Pattern")
        pattern_name = pnode.text("Name") if pnode is not None else ""
        part_type = int(rec.scalar("PartType", 0))

        parts.append(
            {
                "refdes": ref,
                "name": rec.text("Name"),
                "value": rec.text("Value"),
                "pattern": pattern_name,
                "part_type": part_type,
            }
        )

    return parts, bool(tq.node.get("clean_eof", False))


def _parts_from_heuristic_model(dch_path: Path) -> tuple[list[dict[str, object]], bool]:
    model = decode_model_heuristic(Path(dch_path), aggressive_names=False, recover_lines=False)
    comps = model.get("components", []) if isinstance(model, dict) else []
    parts: list[dict[str, object]] = []
    for c in comps if isinstance(comps, list) else []:
        if not isinstance(c, dict):
            continue
        ref = str(c.get("ref", "")).strip()
        if ref == "":
            continue
        pattern = c.get("pattern", {})
        pname = ""
        if isinstance(pattern, dict):
            pname = str(pattern.get("name", "")).strip()
        parts.append(
            {
                "refdes": ref,
                "name": str(c.get("name", "")).strip(),
                "value": str(c.get("value", "")).strip(),
                "pattern": pname,
                "part_type": int(c.get("type", 0) or 0),
            }
        )
    return parts, True


def build_bom(dch_path: Path, backend: str = "structural") -> tuple[list[dict[str, str]], bool]:
    b = str(backend).strip().lower()
    if b == "heuristic":
        parts, clean_eof = _parts_from_heuristic_model(dch_path)
    else:
        decoder, _encoder = backend_codec_pair(b)
        parts, clean_eof = _parts_from_tree_model(decoder(dch_path))
    return group_bom(parts), clean_eof


def backend_codec_pair(backend: str) -> tuple[Callable[[Path], dict[str, object]], Callable[[dict[str, object]], bytes] | None]:
    b = str(backend).strip().lower()
    if b == "structural":
        return decode_structural_components, encode_structural_tree
    if b == "heuristic":
        raise RuntimeError("heuristic backend is decode-only")
    raise RuntimeError(f"unknown backend: {backend}")

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Build BOM CSV from one DipTrace .dch. Groups by Name+Value+Pattern and merges RefDes."
    )
    ap.add_argument("input_dch", help="Input DipTrace schematic binary (.dch)")
    ap.add_argument("output_csv", help="Output BOM CSV path")
    ap.add_argument(
        "--backend",
        choices=["structural", "heuristic"],
        default="structural",
        help="Decoder backend (default: structural).",
    )
    ap.add_argument(
        "--verify-roundtrip",
        action="store_true",
        help="For tree backends, decode+encode and verify byte-equality before BOM export.",
    )
    args = ap.parse_args()

    inp = Path(args.input_dch)
    out = Path(args.output_csv)
    if not inp.exists():
        raise SystemExit(f"input not found: {inp}")

    if bool(args.verify_roundtrip) and args.backend == "structural":
        dec, enc = backend_codec_pair(args.backend)
        tree = dec(inp)
        out_data = enc(tree) if enc is not None else b""
        src_data = inp.read_bytes()
        if out_data != src_data:
            raise RuntimeError(
                f"roundtrip mismatch for backend={args.backend}: "
                f"src={len(src_data)} bytes out={len(out_data)} bytes"
            )

    rows, _clean_eof = build_bom(inp, backend=args.backend)
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
