from __future__ import annotations

"""Profile embedded text-bearing block anchors inside outer opcode records.

Intended use:
- investigate record-local struct-valued fields that are not outer layer2 records
- compare repeated local token contexts around deep text atoms
- support generalization across multiple record families
"""

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.deprecated.pre_shared_model.lib.opcode import decode_opcode_structure_tree


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Profile embedded block anchors inside opcode records")
    ap.add_argument("inputs", nargs="+", help="Input .dch files")
    ap.add_argument("--signature", dest="signature_hex", default="", help="Restrict to one outer record signature")
    ap.add_argument("--min-slot", type=int, default=50, help="Only inspect text atoms at or after this atom index")
    ap.add_argument("--prev", type=int, default=6, help="Number of preceding atoms to include in anchor context")
    ap.add_argument("--next", type=int, default=4, help="Number of following atoms to include in anchor context")
    ap.add_argument("--top", type=int, default=30, help="Number of anchor groups to print")
    return ap


def main() -> int:
    args = build_parser().parse_args()
    signature_hex = str(args.signature_hex).strip()
    anchor_counts: Counter[tuple[object, ...]] = Counter()
    anchor_examples: dict[tuple[object, ...], list[tuple[str, int, str]]] = defaultdict(list)

    input_paths: list[Path] = []
    for item in args.inputs:
        if any(ch in item for ch in "*?[]"):
            input_paths.extend(sorted(Path().glob(item)))
        else:
            input_paths.append(Path(item))

    for path in input_paths:
        tokens, stream, tree = decode_opcode_structure_tree(path)
        for node in tree.iter_nodes():
            if signature_hex and str(node.record.signature_hex) != signature_hex:
                continue
            token_slices = node.token_slices
            for slot, tok in enumerate(token_slices):
                if tok.text is None or slot < int(args.min_slot):
                    continue
                prev_atoms = token_slices[max(0, slot - int(args.prev)) : slot]
                next_atoms = token_slices[slot + 1 : slot + 1 + int(args.next)]
                key = (
                    str(node.record.signature_hex),
                    int(slot),
                    tuple((t.kind, t.value) for t in prev_atoms),
                    tuple((t.kind, t.value) for t in next_atoms),
                )
                anchor_counts[key] += 1
                if len(anchor_examples[key]) < 3:
                    anchor_examples[key].append((path.name, int(node.record.index), str(tok.text)))

    for key, count in anchor_counts.most_common(int(args.top)):
        sig, slot, prev_atoms, next_atoms = key
        print(f"count={count} signature={sig} slot={slot}")
        print(f"  prev={prev_atoms}")
        print(f"  next={next_atoms}")
        print(f"  examples={anchor_examples[key]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
