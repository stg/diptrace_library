from __future__ import annotations

"""Legacy candidate-tree builder for the old framing export.

This script is retained only so earlier exploratory artifacts can still be
reproduced. It is not part of the live opcode layer2 model.
"""

import argparse
import json
from pathlib import Path
from typing import Any


def _build_tree(records: list[dict[str, Any]]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    roots: list[int] = []
    parent_of: dict[int, int | None] = {}
    last_idx: int | None = None
    hint_counts: dict[str, int] = {"root": 0, "child_of_prev": 0, "sibling": 0}

    for r in records:
        idx = int(r.get("index", len(nodes)))
        hint = str(r.get("depth_hint", "sibling"))
        if hint not in hint_counts:
            hint_counts[hint] = 0
        hint_counts[hint] += 1
        if hint == "root" or last_idx is None:
            parent = None
        elif hint == "child_of_prev":
            parent = int(last_idx)
        else:
            parent = parent_of.get(int(last_idx))

        node = {
            "index": idx,
            "start": int(r.get("start", -1)),
            "end": int(r.get("end", -1)),
            "length": int(r.get("length", -1)),
            "tier": str(r.get("tier", "")),
            "decoded_type_hint": str(r.get("decoded_type_hint", "")),
            "header": r.get("header", {}),
            "probe_markers": r.get("probe_markers", {}),
            "children": [],
        }
        nodes.append(node)
        parent_of[idx] = parent
        if parent is None:
            roots.append(idx)
        else:
            # Parent index equals prior record index in this construction.
            ppos = parent
            if 0 <= ppos < len(nodes):
                nodes[ppos]["children"].append(idx)
            else:
                roots.append(idx)
                parent_of[idx] = None

        last_idx = idx

    # Depth map.
    depth: dict[int, int] = {}
    for i in range(len(nodes)):
        d = 0
        p = parent_of.get(i)
        guard = 0
        while p is not None and guard < len(nodes) + 2:
            d += 1
            p = parent_of.get(int(p))
            guard += 1
        depth[i] = d
        nodes[i]["depth"] = d

    return {
        "roots": roots,
        "nodes": nodes,
        "summary": {
            "node_count": len(nodes),
            "root_count": len(roots),
            "max_depth": max(depth.values()) if depth else 0,
            "child_edge_count": sum(len(n.get("children", [])) for n in nodes),
            "hint_counts": hint_counts,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Build candidate layer2 tree from layer1 stream.")
    ap.add_argument("--stream-dir", required=True, help="Directory with *.layer1.stream.json")
    ap.add_argument("--out-dir", required=True, help="Output directory")
    args = ap.parse_args()

    sdir = Path(args.stream_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    streams = sorted(sdir.glob("*.layer1.stream.json"))
    manifest: list[dict[str, Any]] = []
    for sp in streams:
        payload = json.loads(sp.read_text(encoding="utf-8"))
        recs = payload.get("records", []) if isinstance(payload, dict) else []
        if not isinstance(recs, list):
            recs = []
        tree = _build_tree(recs)
        out = {
            "source_stream": str(sp),
            "source_file": payload.get("file", ""),
            "summary": tree["summary"],
            "roots": tree["roots"],
            "nodes": tree["nodes"],
        }
        out_path = out_dir / sp.name.replace(".layer1.stream.json", ".layer2.candidate.json")
        out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        manifest.append({"stream": str(sp), "out": str(out_path), "summary": out["summary"]})

    mpath = out_dir / "manifest.json"
    mpath.write_text(json.dumps({"count": len(manifest), "files": manifest}, indent=2), encoding="utf-8")
    total = sum(int(x["summary"]["node_count"]) for x in manifest)
    print(f"wrote={out_dir} files={len(manifest)} nodes={total}")


if __name__ == "__main__":
    main()
