from __future__ import annotations

"""Discover recurring ORUN-led embedded grammar candidates inside opcode records.

This tool is intended for grammar discovery, not semantic decoding. It groups
record-local ORUN start motifs that are not yet claimed by the current
embedded-block extractor.
"""

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.deprecated.pre_shared_model.lib.opcode import decode_opcode_structure_tree


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Discover recurring unclaimed ORUN-led embedded grammar candidates.")
    ap.add_argument("inputs", nargs="+", help="Input .dch files")
    ap.add_argument("--window", type=int, default=8, help="Number of atoms to capture from each ORUN start")
    ap.add_argument("--top", type=int, default=30, help="Number of motifs to print")
    return ap


def main() -> int:
    args = build_parser().parse_args()
    paths: list[Path] = []
    for item in args.inputs:
        if any(ch in item for ch in "*?[]"):
            paths.extend(sorted(Path().glob(item)))
        else:
            paths.append(Path(item))

    motifs: Counter[tuple[tuple[str, object], ...]] = Counter()
    examples: dict[tuple[tuple[str, object], ...], list[tuple[str, str, int, int]]] = defaultdict(list)
    span_counts: dict[tuple[tuple[str, object], ...], Counter[int]] = defaultdict(Counter)
    next_counts: dict[tuple[tuple[str, object], ...], Counter[tuple[tuple[str, object], ...]]] = defaultdict(Counter)

    for path in paths:
        _tokens, _stream, tree = decode_opcode_structure_tree(path)
        for node in tree.iter_nodes():
            claimed = [(emb.start_atom, emb.end_atom) for emb in node.embedded_children]
            for i, tok in enumerate(node.token_slices):
                if str(tok.kind) != "ORUN":
                    continue
                if any(start <= i <= end for start, end in claimed):
                    continue
                motif = tuple(
                    (str(x.kind), "TEXT" if x.text is not None else x.value)
                    for x in node.token_slices[i : i + int(args.window)]
                )
                motifs[motif] += 1
                next_orun = None
                for j in range(i + 1, len(node.token_slices)):
                    if str(node.token_slices[j].kind) == "ORUN":
                        next_orun = j
                        break
                if next_orun is not None:
                    span_counts[motif][int(next_orun - i)] += 1
                    next_counts[motif][
                        tuple(
                            (str(x.kind), "TEXT" if x.text is not None else x.value)
                            for x in node.token_slices[next_orun : next_orun + int(args.window)]
                        )
                    ] += 1
                if len(examples[motif]) < 3:
                    examples[motif].append((path.name, str(node.record.signature_hex), int(node.record.index), int(i)))

    for motif, count in motifs.most_common(int(args.top)):
        print(f"count={count} motif={motif}")
        print(f"  spans={span_counts[motif].most_common(6)}")
        print(f"  next={next_counts[motif].most_common(4)}")
        print(f"  examples={examples[motif]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
