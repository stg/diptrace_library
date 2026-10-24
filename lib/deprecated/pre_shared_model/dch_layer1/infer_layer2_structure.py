from __future__ import annotations

import argparse
import json
from bisect import bisect_right
from collections import Counter, defaultdict
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.deprecated.pre_shared_model.lib.opcode.layer1 import parse_layer1_events, read_bytes
from lib.deprecated.pre_shared_model.lib.structural.decoder import decode_structural_components, decode_structural_records


def _walk_tree_nodes(
    node: dict[str, Any],
    *,
    parent_offset: int | None,
    parent_type: str | None,
    depth: int,
    out: list[dict[str, Any]],
) -> None:
    ni = node.get("_internal", {}) if isinstance(node.get("_internal"), dict) else {}
    off = ni.get("offset")
    end = ni.get("end_offset")
    if isinstance(off, int) and isinstance(end, int) and off >= 0 and end > off:
        out.append(
            {
                "offset": int(off),
                "end_offset": int(end),
                "length": int(end - off),
                "type": str(node.get("type", "")),
                "parent_offset": int(parent_offset) if isinstance(parent_offset, int) else None,
                "parent_type": str(parent_type) if parent_type else "",
                "depth": int(depth),
            }
        )
        parent_offset = int(off)
        parent_type = str(node.get("type", ""))

    for ch in node.get("children", []) if isinstance(node.get("children"), list) else []:
        if isinstance(ch, dict):
            _walk_tree_nodes(ch, parent_offset=parent_offset, parent_type=parent_type, depth=depth + 1, out=out)


def _header8_hex(data: bytes, start: int) -> str:
    return data[start : min(start + 8, len(data))].hex(" ")


def _header7_hex(data: bytes, start: int) -> str:
    s = start + 1
    return data[s : min(s + 7, len(data))].hex(" ")


def _header_triplet(data: bytes, start: int) -> str:
    if start + 7 >= len(data):
        return ""
    return (
        f"b0={data[start]:02x},b1={data[start + 1]:02x},b2={data[start + 2]:02x},"
        f"lead={data[start + 5]:02x},mode={data[start + 6]:02x},b7={data[start + 7]:02x}"
    )


def _token_location(tokens: list[dict[str, Any]], starts: list[int], offset: int) -> dict[str, Any]:
    i = bisect_right(starts, offset) - 1
    if i < 0 or i >= len(tokens):
        return {"token_index": -1, "token_kind": "", "token_value": None, "intra_offset": -1}
    t = tokens[i]
    if not (int(t["start"]) <= offset < int(t["end"])):
        return {"token_index": -1, "token_kind": "", "token_value": None, "intra_offset": -1}
    return {
        "token_index": int(i),
        "token_kind": str(t["kind"]),
        "token_value": t.get("value"),
        "intra_offset": int(offset - int(t["start"])),
    }


def infer_for_file(path: Path) -> dict[str, Any]:
    data = read_bytes(path)
    toks = [t.as_dict() for t in parse_layer1_events(data)]
    tok_starts = [int(t["start"]) for t in toks]

    tree = decode_structural_components(path)
    tree_nodes: list[dict[str, Any]] = []
    _walk_tree_nodes(tree, parent_offset=None, parent_type=None, depth=0, out=tree_nodes)
    by_offset = {int(n["offset"]): n for n in tree_nodes}

    top_records = decode_structural_records(data)
    objects: list[dict[str, Any]] = []
    for i, r in enumerate(top_records):
        start = int(r.start)
        end = int(r.end)
        semantic_start = start + 1
        n = by_offset.get(start, {})
        loc = _token_location(toks, tok_starts, semantic_start)
        objects.append(
            {
                "index": int(i),
                "offset": start,
                "semantic_start": semantic_start,
                "end_offset": end,
                "length": int(end - start),
                "reference_type_hint": str(n.get("type", "")),
                "reference_parent_offset": n.get("parent_offset"),
                "reference_parent_type_hint": str(n.get("parent_type", "")),
                "reference_depth_hint": int(n.get("depth", -1)),
                "header8_hex": _header8_hex(data, start),
                "header7_hex": _header7_hex(data, start),
                "prefix_byte_hex": f"{data[start]:02x}" if start < len(data) else "",
                "header_triplet": _header_triplet(data, start),
                "token_location": loc,
                "start_bytes_16": data[start : min(start + 16, len(data))].hex(" "),
            }
        )

    return {
        "file": str(path),
        "size": len(data),
        "token_count": len(toks),
        "object_count": len(objects),
        "objects": objects,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Infer layer2 opaque object structure from binary headers and tree offsets.")
    ap.add_argument("--samples", required=True, help="Directory with .dch files")
    ap.add_argument("--out", required=True, help="Output JSON file")
    args = ap.parse_args()

    sdir = Path(args.samples)
    files = sorted(sdir.glob("*.dch"))
    per_file = [infer_for_file(fp) for fp in files]

    kind_counts: Counter[str] = Counter()
    kind_types: dict[str, Counter[str]] = defaultdict(Counter)
    kind_triplets: Counter[str] = Counter()
    kind_token_sites: dict[str, Counter[str]] = defaultdict(Counter)
    edge_counts: Counter[str] = Counter()
    prefix_by_kind: dict[str, Counter[str]] = defaultdict(Counter)
    global_start_sites: Counter[str] = Counter()
    relation_mode_counts: Counter[str] = Counter()
    kind_roles: dict[str, Counter[str]] = defaultdict(Counter)
    parent_distance_counts: Counter[int] = Counter()
    header_tail_roles: dict[str, Counter[str]] = defaultdict(Counter)
    child_by_parent_kind: dict[str, Counter[str]] = defaultdict(Counter)

    for rep in per_file:
        by_off = {int(o["offset"]): o for o in rep["objects"]}
        by_index = {int(o["index"]): o for o in rep["objects"]}
        for obj in rep["objects"]:
            kind = str(obj["header7_hex"])
            kind_counts[kind] += 1
            prefix_by_kind[kind][str(obj.get("prefix_byte_hex", ""))] += 1
            kind_triplets[str(obj["header_triplet"])] += 1
            tloc = obj.get("token_location", {})
            site = f"{tloc.get('token_kind','')}+{int(tloc.get('intra_offset', -1))}"
            kind_token_sites[kind][site] += 1
            global_start_sites[site] += 1
            th = str(obj.get("reference_type_hint", "") or "Unknown")
            kind_types[kind][th] += 1
            header8 = bytes.fromhex(kind)
            tail = f"{header8[6]:02x} {header8[7]:02x}" if len(header8) >= 8 else ""
            poff = obj.get("reference_parent_offset")
            if isinstance(poff, int) and poff in by_off:
                pk = str(by_off[poff]["header8_hex"])
                parent_kind7 = str(by_off[poff]["header7_hex"])
                edge_counts[f"{parent_kind7} -> {kind}"] += 1
                kind_roles[kind]["child"] += 1
                kind_roles[parent_kind7]["parent"] += 1
                child_by_parent_kind[parent_kind7][kind] += 1
                parent = by_off[poff]
                parent_distance_counts[int(obj["index"]) - int(parent["index"])] += 1
                header_tail_roles[tail]["child"] += 1
                if int(obj["offset"]) >= int(parent["end_offset"]):
                    relation_mode_counts["after"] += 1
                elif int(obj["end_offset"]) <= int(parent["end_offset"]):
                    relation_mode_counts["inside"] += 1
                else:
                    relation_mode_counts["overlap"] += 1
            else:
                kind_roles[kind]["root"] += 1
                header_tail_roles[tail]["root"] += 1

        # Track the simple record-stream adjacency independent of parent hints.
        for i in range(len(rep["objects"]) - 1):
            cur = by_index.get(i)
            nxt = by_index.get(i + 1)
            if not isinstance(cur, dict) or not isinstance(nxt, dict):
                continue

    kind_ids = {k: f"O{idx:03d}" for idx, (k, _n) in enumerate(kind_counts.most_common(), start=1)}

    for rep in per_file:
        for obj in rep["objects"]:
            obj["object_kind_id"] = kind_ids[str(obj["header7_hex"])]
            poff = obj.get("reference_parent_offset")
            if isinstance(poff, int):
                parent = next((x for x in rep["objects"] if int(x["offset"]) == poff), None)
                obj["parent_kind_id"] = str(parent["object_kind_id"]) if isinstance(parent, dict) else ""
            else:
                obj["parent_kind_id"] = ""

    payload = {
        "samples_dir": str(sdir),
        "file_count": len(per_file),
        "object_kind_count": len(kind_ids),
        "files": per_file,
        "object_kinds": [
            {
                "id": kind_ids[k],
                "header7_hex": k,
                "count": int(n),
                "prefix_counts": dict(sorted(prefix_by_kind[k].items(), key=lambda item: item[1], reverse=True)),
                "type_hints_top": [{"type": t, "count": c} for t, c in kind_types[k].most_common(8)],
                "token_site_top": [{"site": s, "count": c} for s, c in kind_token_sites[k].most_common(8)],
                "role_counts": dict(kind_roles[k]),
            }
            for k, n in kind_counts.most_common()
        ],
        "header_triplets_top": [{"triplet": k, "count": v} for k, v in kind_triplets.most_common(32)],
        "start_sites_top": [{"site": k, "count": v} for k, v in global_start_sites.most_common(32)],
        "edge_counts_top": [{"edge": k, "count": v} for k, v in edge_counts.most_common(64)],
        "summary": {
            "object_total": sum(int(r["object_count"]) for r in per_file),
            "kind_total": len(kind_ids),
            "relation_mode_counts": dict(relation_mode_counts),
            "parent_distance_counts": dict(parent_distance_counts),
        },
        "header_tail_roles": [
            {"tail": tail, "roles": dict(counts)}
            for tail, counts in sorted(header_tail_roles.items(), key=lambda item: sum(item[1].values()), reverse=True)
        ],
        "parent_child_model": [
            {
                "parent_kind_id": kind_ids[parent_kind],
                "parent_header7_hex": parent_kind,
                "children_top": [
                    {
                        "child_kind_id": kind_ids[child_kind],
                        "child_header7_hex": child_kind,
                        "count": count,
                    }
                    for child_kind, count in counts.most_common(8)
                ],
            }
            for parent_kind, counts in sorted(
                child_by_parent_kind.items(),
                key=lambda item: sum(item[1].values()),
                reverse=True,
            )
        ],
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(
        f"wrote={out} files={len(per_file)} objects={payload['summary']['object_total']} kinds={len(kind_ids)}"
    )


if __name__ == "__main__":
    main()
