from __future__ import annotations

"""Stress-test embedded opcode grammar over a large DCH corpus.

This tool validates the record-local embedded block grammar discovered in the
clean opcode pipeline. It reports:
- embedded family totals
- embedded sequence shapes by outer signature and by layer2 triplet
- failures while decoding outer layer2/layer3
"""

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.deprecated.pre_shared_model.lib.opcode import decode_opcode_structure_tree


def _worker(path_str: str) -> dict:
    path = Path(path_str)
    tokens, stream, tree = decode_opcode_structure_tree(path)
    embedded_totals = Counter(node.structure_type for node in tree.iter_embedded_nodes())
    triplet_sequences = Counter()
    signature_sequences = Counter()
    embedded_atom_counts = Counter()

    for node in tree.iter_nodes():
        rec = node.record
        triplet = (int(rec.class_byte), int(rec.record_code), str(rec.tail_class))
        sequence = tuple(str(emb.structure_type) for emb in node.embedded_children)
        signature_sequences[(str(rec.signature_hex), sequence)] += 1
        triplet_sequences[(triplet, sequence)] += 1
        for emb in node.embedded_children:
            embedded_atom_counts[(str(emb.structure_type), int(emb.end_atom - emb.start_atom + 1))] += 1

    return {
        "file": str(path),
        "embedded_totals": dict(embedded_totals),
        "triplet_sequences": [
            {"triplet": [triplet[0], triplet[1], triplet[2]], "sequence": list(sequence), "count": int(count)}
            for (triplet, sequence), count in triplet_sequences.items()
        ],
        "signature_sequences": [
            {"signature": signature, "sequence": list(sequence), "count": int(count)}
            for (signature, sequence), count in signature_sequences.items()
        ],
        "embedded_atom_counts": [
            {"structure_type": structure_type, "atom_count": int(atom_count), "count": int(count)}
            for (structure_type, atom_count), count in embedded_atom_counts.items()
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Stress-test embedded opcode grammar on a DCH corpus.")
    ap.add_argument("--root", required=True, help="Root directory to search for .dch files")
    ap.add_argument("--workers", type=int, default=8, help="Number of worker processes")
    ap.add_argument("--progress-sec", type=float, default=10.0, help="Progress print interval")
    ap.add_argument("--out", required=True, help="Output JSON path")
    return ap


def main() -> int:
    args = build_parser().parse_args()
    root = Path(args.root)
    files = sorted(root.rglob("*.dch"))

    embedded_totals: Counter[str] = Counter()
    triplet_sequences: Counter[tuple[tuple[int, int, str], tuple[str, ...]]] = Counter()
    signature_sequences: Counter[tuple[str, tuple[str, ...]]] = Counter()
    embedded_atom_counts: Counter[tuple[str, int]] = Counter()
    failures: list[dict[str, str]] = []

    t0 = time.time()
    last_progress = t0

    with ProcessPoolExecutor(max_workers=int(args.workers)) as ex:
        futures = [ex.submit(_worker, str(path)) for path in files]
        for i, fut in enumerate(as_completed(futures), 1):
            try:
                res = fut.result()
            except Exception as exc:  # pragma: no cover - failure path
                failures.append({"file": "<worker>", "error": repr(exc)})
            else:
                embedded_totals.update({str(k): int(v) for k, v in res["embedded_totals"].items()})
                for row in res["triplet_sequences"]:
                    triplet = tuple(row["triplet"])  # type: ignore[arg-type]
                    sequence = tuple(str(x) for x in row["sequence"])
                    triplet_sequences[(triplet, sequence)] += int(row["count"])
                for row in res["signature_sequences"]:
                    signature_sequences[(str(row["signature"]), tuple(str(x) for x in row["sequence"]))] += int(row["count"])
                for row in res["embedded_atom_counts"]:
                    embedded_atom_counts[(str(row["structure_type"]), int(row["atom_count"]))] += int(row["count"])

            now = time.time()
            if now - last_progress >= float(args.progress_sec) or i == len(futures):
                print(f"progress files={i}/{len(futures)} failures={len(failures)} elapsed={now - t0:.1f}s")
                last_progress = now

    payload = {
        "root": str(root),
        "file_count": len(files),
        "failure_count": len(failures),
        "failures": failures,
        "embedded_totals": dict(embedded_totals.most_common()),
        "triplet_sequences_top": [
            {
                "triplet": [triplet[0], triplet[1], triplet[2]],
                "sequence": list(sequence),
                "count": int(count),
            }
            for (triplet, sequence), count in triplet_sequences.most_common(128)
        ],
        "signature_sequences_top": [
            {
                "signature": signature,
                "sequence": list(sequence),
                "count": int(count),
            }
            for (signature, sequence), count in signature_sequences.most_common(128)
        ],
        "embedded_atom_counts_top": [
            {"structure_type": structure_type, "atom_count": int(atom_count), "count": int(count)}
            for (structure_type, atom_count), count in embedded_atom_counts.most_common(128)
        ],
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
