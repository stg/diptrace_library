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
    ap = argparse.ArgumentParser(description="Profile a parent/child opcode structure pair across one or more DCH files.")
    ap.add_argument("paths", nargs="+", help="Input .dch files")
    ap.add_argument("--parent-signature", help="Exact parent structure signature hex")
    ap.add_argument("--child-signature", help="Exact child structure signature hex")
    ap.add_argument("--parent-header7", help="Compatibility alias for --parent-signature")
    ap.add_argument("--child-header7", help="Compatibility alias for --child-signature")
    ap.add_argument("--top", type=int, default=12, help="Rows to print")
    ap.add_argument("--examples", type=int, default=4, help="Example pairs to print")
    args = ap.parse_args()
    parent_signature = args.parent_signature or args.parent_header7
    child_signature = args.child_signature or args.child_header7
    if not parent_signature or not child_signature:
        ap.error("parent and child signatures are required")

    total_parents = 0
    exact_pair = 0
    parent_textsig_counter: Counter[tuple[tuple[int, str], ...]] = Counter()
    parent_prefixsig_counter: Counter[tuple[str, ...]] = Counter()
    child_prefixsig_counter: Counter[tuple[str, ...]] = Counter()
    pair_lengths_counter: Counter[tuple[int, int]] = Counter()
    examples: list[tuple[str, object, object]] = []

    for raw_path in args.paths:
        path = Path(raw_path)
        _tokens, _stream, tree = decode_opcode_structure_tree(path)
        for parent in tree.find_by_signature(parent_signature):
            total_parents += 1
            matching_children = [child for child in parent.children if str(child.record.signature_hex) == child_signature]
            if len(parent.children) == 1 and len(matching_children) == 1:
                exact_pair += 1
                child = matching_children[0]
                parent_textsig = tuple((idx, tok.kind) for idx, tok in enumerate(parent.token_slices) if tok.text is not None)
                parent_prefixsig = tuple(tok.kind for tok in parent.token_slices[:24])
                child_prefixsig = tuple(tok.kind for tok in child.token_slices[:24])
                parent_textsig_counter[parent_textsig] += 1
                parent_prefixsig_counter[parent_prefixsig] += 1
                child_prefixsig_counter[child_prefixsig] += 1
                pair_lengths_counter[(int(parent.record.raw_length), int(child.record.raw_length))] += 1
                if len(examples) < args.examples:
                    examples.append((str(path), parent, child))

    print(f"parent_signature={parent_signature}")
    print(f"child_signature={child_signature}")
    print(f"parents={total_parents}")
    print(f"exact_single_child_pairs={exact_pair}")

    print("parent_text_signatures:")
    for sig, count in parent_textsig_counter.most_common(args.top):
        rendered = ", ".join(f"{idx}:{kind}" for idx, kind in sig) if sig else "<none>"
        print(f"  {count:6d} {rendered}")

    print("parent_prefix_signatures:")
    for sig, count in parent_prefixsig_counter.most_common(args.top):
        print(f"  {count:6d} {' | '.join(sig)}")

    print("child_prefix_signatures:")
    for sig, count in child_prefixsig_counter.most_common(args.top):
        print(f"  {count:6d} {' | '.join(sig)}")

    print("pair_lengths:")
    for lengths, count in pair_lengths_counter.most_common(args.top):
        print(f"  {count:6d} parent_raw={lengths[0]} child_raw={lengths[1]}")

    print("examples:")
    for sample_path, parent, child in examples:
        parent_texts = [(idx, tok.kind, tok.text) for idx, tok in enumerate(parent.token_slices) if tok.text is not None][:8]
        print(
            f"  file={sample_path} parent={parent.record.index} child={child.record.index} "
            f"parent_raw={parent.record.raw_length} child_raw={child.record.raw_length}"
        )
        print(f"    parent_texts={parent_texts}")


if __name__ == "__main__":
    main()
