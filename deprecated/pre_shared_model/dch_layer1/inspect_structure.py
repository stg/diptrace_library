from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.deprecated.pre_shared_model.lib.opcode import decode_opcode_structure_tree


def _iter_selected_nodes(tree, *, record_index: int | None, descriptor_id: str | None, signature_hex: str | None, role: str | None):
    for node in tree.iter_nodes():
        if record_index is not None and int(node.record.index) != int(record_index):
            continue
        if descriptor_id is not None and str(node.descriptor.descriptor_id) != str(descriptor_id):
            continue
        if signature_hex is not None and str(node.record.signature_hex) != str(signature_hex):
            continue
        if role is not None and node.prop("Role") != role:
            continue
        yield node


def main() -> None:
    ap = argparse.ArgumentParser(description="Inspect clean opcode structure-tree nodes and token slices.")
    ap.add_argument("dch", help="Input .dch file")
    ap.add_argument("--record-index", type=int, help="Filter to one record index")
    ap.add_argument("--descriptor", help="Filter by descriptor id")
    ap.add_argument("--signature", help="Filter by exact structure signature hex")
    ap.add_argument("--header7", help="Compatibility alias for --signature")
    ap.add_argument("--role", help="Filter by exact Role property")
    ap.add_argument("--limit", type=int, default=8, help="Max nodes to print")
    args = ap.parse_args()

    path = Path(args.dch)
    _tokens, _stream, tree = decode_opcode_structure_tree(path)
    shown = 0

    for node in _iter_selected_nodes(
        tree,
        record_index=args.record_index,
        descriptor_id=args.descriptor,
        signature_hex=args.signature or args.header7,
        role=args.role,
    ):
        print(
            f"record={node.record.index} depth={node.depth} "
            f"parent={node.parent_record_index} "
            f"descriptor={node.descriptor.descriptor_id} "
            f"type={node.structure_type}"
        )
        print(
            f"  signature={node.record.signature_hex} prefix={node.record.prefix_byte:02x} "
            f"tail={node.record.tail_class} raw={node.record.raw_length} "
            f"semantic={node.record.semantic_length}"
        )
        if node.properties:
            print("  properties:")
            for key, value in sorted(node.properties.items()):
                print(f"    {key}={value}")
        if node.token_slices:
            print("  token_slices:")
            for tok in node.token_slices:
                text = f" text={tok.text!r}" if tok.text is not None else ""
                value = f" value={tok.value}" if tok.value is not None else ""
                print(
                    f"    [{tok.token_index}] {tok.kind} "
                    f"{tok.start}:{tok.end} trim={tok.start_trim}:{tok.end_trim}"
                    f"{value}{text}"
                )
        if node.children:
            print(f"  children={[int(child.record.index) for child in node.children]}")
        shown += 1
        if shown >= int(args.limit):
            break

    print(f"shown={shown}")


if __name__ == "__main__":
    main()
