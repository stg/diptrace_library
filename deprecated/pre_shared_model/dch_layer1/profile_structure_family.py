from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.deprecated.pre_shared_model.lib.opcode import decode_opcode_structure_tree


def _token_signature(node, limit: int) -> tuple[str, ...]:
    return tuple(tok.kind for tok in node.token_slices[:limit])


def _text_signature(node) -> tuple[tuple[int, str], ...]:
    out: list[tuple[int, str]] = []
    for idx, tok in enumerate(node.token_slices):
        if tok.text is not None:
            out.append((idx, tok.kind))
    return tuple(out)


def _text_examples(node, limit: int) -> list[tuple[int, str, str]]:
    out: list[tuple[int, str, str]] = []
    for idx, tok in enumerate(node.token_slices):
        if tok.text is not None:
            out.append((idx, tok.kind, tok.text))
            if len(out) >= limit:
                break
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Profile one opcode structure family across one or more DCH files.")
    ap.add_argument("paths", nargs="+", help="Input .dch files")
    ap.add_argument("--signature", help="Exact structure signature hex to profile")
    ap.add_argument("--header7", help="Compatibility alias for --signature")
    ap.add_argument("--sig-tokens", type=int, default=24, help="Token count for prefix signature clustering")
    ap.add_argument("--top", type=int, default=12, help="Rows to print per section")
    ap.add_argument("--examples", type=int, default=3, help="Example nodes to print")
    args = ap.parse_args()
    signature_hex = args.signature or args.header7
    if not signature_hex:
        ap.error("one of --signature or --header7 is required")

    total_nodes = 0
    prefix_counter: Counter[tuple[str, ...]] = Counter()
    textsig_counter: Counter[tuple[tuple[int, str], ...]] = Counter()
    parent_counter: Counter[str] = Counter()
    child_counter: Counter[str] = Counter()
    childset_counter: Counter[tuple[str, ...]] = Counter()
    example_nodes: list[tuple[str, object]] = []
    example_by_prefix: dict[tuple[str, ...], tuple[str, object]] = {}
    example_by_textsig: dict[tuple[tuple[int, str], ...], tuple[str, object]] = {}
    raw_lengths: list[int] = []
    semantic_lengths: list[int] = []

    for raw_path in args.paths:
        path = Path(raw_path)
        _tokens, _stream, tree = decode_opcode_structure_tree(path)
        nodes = tree.find_by_signature(signature_hex)
        for node in nodes:
            total_nodes += 1
            raw_lengths.append(int(node.record.raw_length))
            semantic_lengths.append(int(node.record.semantic_length))
            prefix = _token_signature(node, args.sig_tokens)
            textsig = _text_signature(node)
            parent_header = "" if node.parent_record_index is None else str(tree.find_by_record_index(node.parent_record_index).record.signature_hex)
            child_headers = tuple(sorted(str(child.record.signature_hex) for child in node.children))

            prefix_counter[prefix] += 1
            textsig_counter[textsig] += 1
            parent_counter[parent_header] += 1
            for child_header in child_headers:
                child_counter[child_header] += 1
            childset_counter[child_headers] += 1

            example_by_prefix.setdefault(prefix, (str(path), node))
            example_by_textsig.setdefault(textsig, (str(path), node))
            if len(example_nodes) < args.examples:
                example_nodes.append((str(path), node))

    print(f"signature={signature_hex}")
    print(f"nodes={total_nodes}")
    if raw_lengths:
        print(
            f"raw_length min={min(raw_lengths)} max={max(raw_lengths)} "
            f"avg={sum(raw_lengths)/len(raw_lengths):.1f}"
        )
    if semantic_lengths:
        print(
            f"semantic_length min={min(semantic_lengths)} max={max(semantic_lengths)} "
            f"avg={sum(semantic_lengths)/len(semantic_lengths):.1f}"
        )

    print("parent_headers:")
    for header, count in parent_counter.most_common(args.top):
        print(f"  {count:6d} {header or '<root>'}")

    print("child_headers:")
    for header, count in child_counter.most_common(args.top):
        print(f"  {count:6d} {header}")

    print("child_sets:")
    for childset, count in childset_counter.most_common(args.top):
        rendered = ", ".join(childset) if childset else "<none>"
        print(f"  {count:6d} {rendered}")

    print("token_prefix_signatures:")
    for prefix, count in prefix_counter.most_common(args.top):
        print(f"  {count:6d} {' | '.join(prefix)}")

    print("text_signatures:")
    for textsig, count in textsig_counter.most_common(args.top):
        rendered = ", ".join(f"{idx}:{kind}" for idx, kind in textsig) if textsig else "<none>"
        print(f"  {count:6d} {rendered}")

    print("examples:")
    for sample_path, node in example_nodes:
        parent = "<root>" if node.parent_record_index is None else str(node.parent_record_index)
        print(
            f"  file={sample_path} record={node.record.index} depth={node.depth} "
            f"parent={parent} children={[int(c.record.index) for c in node.children]}"
        )
        print(f"    texts={ascii(_text_examples(node, 10))}")


if __name__ == "__main__":
    main()
