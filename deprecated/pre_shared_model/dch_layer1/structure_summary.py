from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.deprecated.pre_shared_model.lib.opcode import decode_opcode_structure_tree


def main() -> None:
    ap = argparse.ArgumentParser(description="Summarize opcode layer3 structure tree for a DCH file.")
    ap.add_argument("dch", help="Input .dch file")
    ap.add_argument("--top", type=int, default=12, help="Number of top structure/descriptor counts to print")
    args = ap.parse_args()

    path = Path(args.dch)
    _tokens, stream, tree = decode_opcode_structure_tree(path)
    node_count = sum(1 for _ in tree.iter_nodes())
    role_counts: dict[str, int] = {}
    for node in tree.iter_nodes():
        role = node.prop("Role")
        if role is not None:
            role_counts[str(role)] = int(role_counts.get(str(role), 0) + 1)

    print(f"file={path}")
    print(f"roots={len(tree.roots)} nodes={node_count} records={len(stream.records)}")
    print("structure_types:")
    for key, count in list(tree.structure_type_counts().items())[: args.top]:
        print(f"  {count:6d} {key}")
    print("descriptors:")
    for key, count in list(tree.descriptor_id_counts().items())[: args.top]:
        print(f"  {count:6d} {key}")
    if role_counts:
        print("roles:")
        for key, count in sorted(role_counts.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"  {count:6d} {key}")


if __name__ == "__main__":
    main()
