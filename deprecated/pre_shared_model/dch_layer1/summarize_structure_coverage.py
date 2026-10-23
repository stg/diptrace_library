from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.deprecated.pre_shared_model.lib.opcode import decode_opcode_structure_tree


def main() -> None:
    ap = argparse.ArgumentParser(description="Summarize promoted-vs-fallback opcode layer3 coverage.")
    ap.add_argument("paths", nargs="+", help="Input .dch files")
    args = ap.parse_args()

    files = [Path(p) for p in args.paths]
    descriptor_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    promoted = 0
    fallback = 0
    nodes = 0

    for path in files:
        _tokens, _stream, tree = decode_opcode_structure_tree(path)
        for node in tree.iter_nodes():
            nodes += 1
            descriptor_id = str(node.descriptor.descriptor_id)
            descriptor_counts[descriptor_id] += 1
            family_counts[str(node.structure_type)] += 1
            if descriptor_id.startswith("OpcodeStructure."):
                fallback += 1
            else:
                promoted += 1

    print(f"files={len(files)} nodes={nodes} promoted={promoted} fallback={fallback}")
    if nodes:
        print(f"promoted_pct={promoted / nodes:.4f} fallback_pct={fallback / nodes:.4f}")
    print("top_descriptors:")
    for key, count in descriptor_counts.most_common(16):
        print(f"  {count:6d} {key}")
    print("top_structure_types:")
    for key, count in family_counts.most_common(16):
        print(f"  {count:6d} {key}")


if __name__ == "__main__":
    main()
