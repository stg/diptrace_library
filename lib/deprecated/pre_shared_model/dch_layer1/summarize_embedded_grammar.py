from __future__ import annotations

"""Summarize record-local embedded grammar across one or more DCH files.

This tool reports structural embedded blocks discovered inside outer opcode
records. It is intended to help answer questions like:
- which outer signatures carry embedded blocks?
- which embedded families recur across those signatures?
- how large are the embedded blocks?
"""

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.deprecated.pre_shared_model.lib.opcode import decode_opcode_structure_tree


def main() -> int:
    ap = argparse.ArgumentParser(description="Summarize embedded opcode grammar across one or more DCH files.")
    ap.add_argument("paths", nargs="+", help="Input .dch files")
    args = ap.parse_args()

    by_outer: dict[str, Counter[str]] = defaultdict(Counter)
    by_embedded_atoms: Counter[tuple[str, int]] = Counter()
    totals: Counter[str] = Counter()

    input_paths: list[Path] = []
    for raw_path in args.paths:
        if any(ch in raw_path for ch in "*?[]"):
            input_paths.extend(sorted(Path().glob(raw_path)))
        else:
            input_paths.append(Path(raw_path))

    for path in input_paths:
        _tokens, _stream, tree = decode_opcode_structure_tree(path)
        for node in tree.iter_nodes():
            outer_sig = str(node.record.signature_hex)
            for embedded in node.iter_embedded_nodes():
                emb_type = str(embedded.structure_type)
                by_outer[outer_sig][emb_type] += 1
                by_embedded_atoms[(emb_type, int(embedded.end_atom - embedded.start_atom + 1))] += 1
                totals[emb_type] += 1

    print("embedded_totals")
    for emb_type, count in totals.most_common():
        print(f"  {count:6d} {emb_type}")

    print("\nby_outer_signature")
    for outer_sig, counts in sorted(by_outer.items(), key=lambda item: (-sum(item[1].values()), item[0])):
        print(f"  {outer_sig}")
        for emb_type, count in counts.most_common():
            print(f"    {count:6d} {emb_type}")

    print("\natom_count_shapes")
    for (emb_type, atom_count), count in by_embedded_atoms.most_common():
        print(f"  {count:6d} atoms={atom_count:2d} {emb_type}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
