from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.deprecated.pre_shared_model.lib.opcode import decode_opcode_structure_tree


def _family_entry() -> dict:
    return {
        "count": 0,
        "root_count": 0,
        "with_text_count": 0,
        "with_children_count": 0,
        "raw_lengths": [],
        "semantic_lengths": [],
        "parent_headers": Counter(),
        "child_headers": Counter(),
        "text_signatures": Counter(),
        "descriptors": Counter(),
        "files": Counter(),
    }


def _compact_family_stats(signature: str, entry: dict) -> dict:
    raw_lengths = [int(v) for v in entry["raw_lengths"]]
    semantic_lengths = [int(v) for v in entry["semantic_lengths"]]
    return {
        "signature": signature,
        "count": int(entry["count"]),
        "root_count": int(entry["root_count"]),
        "with_text_count": int(entry["with_text_count"]),
        "with_children_count": int(entry["with_children_count"]),
        "raw_length_min": min(raw_lengths) if raw_lengths else 0,
        "raw_length_max": max(raw_lengths) if raw_lengths else 0,
        "raw_length_avg": (sum(raw_lengths) / len(raw_lengths)) if raw_lengths else 0.0,
        "semantic_length_min": min(semantic_lengths) if semantic_lengths else 0,
        "semantic_length_max": max(semantic_lengths) if semantic_lengths else 0,
        "semantic_length_avg": (sum(semantic_lengths) / len(semantic_lengths)) if semantic_lengths else 0.0,
        "parent_headers": dict(entry["parent_headers"].most_common(12)),
        "child_headers": dict(entry["child_headers"].most_common(12)),
        "text_signatures": {
            (";".join(f"{idx}:{kind}" for idx, kind in sig) if sig else "<none>"): int(count)
            for sig, count in entry["text_signatures"].most_common(12)
        },
        "descriptors": dict(entry["descriptors"].most_common(8)),
        "files": dict(entry["files"].most_common(12)),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Summarize opcode structure families across one or more DCH files.")
    ap.add_argument("paths", nargs="+", help="Input .dch files")
    ap.add_argument("--out", help="Optional JSON output path")
    ap.add_argument("--top", type=int, default=16, help="Top family rows to print")
    args = ap.parse_args()

    families: dict[str, dict] = defaultdict(_family_entry)

    for raw_path in args.paths:
        path = Path(raw_path)
        _tokens, _stream, tree = decode_opcode_structure_tree(path)
        for node in tree.iter_nodes():
            signature = str(node.record.signature_hex)
            entry = families[signature]
            entry["count"] += 1
            entry["root_count"] += int(node.parent_record_index is None)
            entry["with_text_count"] += int(bool(node.prop("Texts")))
            entry["with_children_count"] += int(bool(node.children))
            entry["raw_lengths"].append(int(node.record.raw_length))
            entry["semantic_lengths"].append(int(node.record.semantic_length))
            entry["parent_headers"][str(node.prop("ParentSignature") or "<root>")] += 1
            for child in node.children:
                entry["child_headers"][str(child.record.signature_hex)] += 1
            textsig = tuple((idx, tok.kind) for idx, tok in enumerate(node.token_slices) if tok.text is not None)
            entry["text_signatures"][textsig] += 1
            entry["descriptors"][str(node.descriptor.descriptor_id)] += 1
            entry["files"][str(path.name)] += 1

    rows = [_compact_family_stats(signature, entry) for signature, entry in families.items()]
    rows.sort(key=lambda row: (-int(row["count"]), str(row["signature"])))

    print(f"families={len(rows)}")
    for row in rows[: int(args.top)]:
        print(
            f"{int(row['count']):6d} "
            f"signature={row['signature']} "
            f"root={row['root_count']} "
            f"text={row['with_text_count']} "
            f"children={row['with_children_count']} "
            f"raw_avg={row['raw_length_avg']:.1f}"
        )

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({"families": rows}, indent=2), encoding="utf-8")
        print(f"wrote={out_path}")


if __name__ == "__main__":
    main()
