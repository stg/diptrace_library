from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.deprecated.pre_shared_model.lib.opcode import decode_opcode_structure_tree


def main() -> None:
    ap = argparse.ArgumentParser(description="Profile text slot frequencies for a structure header family.")
    ap.add_argument("paths", nargs="+", help="Input .dch files")
    ap.add_argument("--signature", help="Target structure signature")
    ap.add_argument("--header7", help="Compatibility alias for --signature")
    ap.add_argument("--top", type=int, default=24, help="Top slots to print")
    ap.add_argument("--values", type=int, default=8, help="Example values per slot")
    args = ap.parse_args()
    signature_hex = args.signature or args.header7
    if not signature_hex:
        ap.error("one of --signature or --header7 is required")

    slot_counts: Counter[int] = Counter()
    slot_kinds: dict[int, Counter[str]] = defaultdict(Counter)
    slot_values: dict[int, Counter[str]] = defaultdict(Counter)
    nodes = 0

    for path_str in args.paths:
        _tokens, _stream, tree = decode_opcode_structure_tree(Path(path_str))
        for node in tree.iter_nodes():
            if str(node.prop("Signature", "")) != str(signature_hex):
                continue
            nodes += 1
            slots = list(node.prop("TextSlots", []))
            kinds = list(node.prop("TextKinds", []))
            values = list(node.prop("Texts", []))
            for idx, slot in enumerate(slots):
                slot_i = int(slot)
                slot_counts[slot_i] += 1
                if idx < len(kinds):
                    slot_kinds[slot_i][str(kinds[idx])] += 1
                if idx < len(values):
                    slot_values[slot_i][str(values[idx])] += 1

    print(f"signature={signature_hex}")
    print(f"nodes={nodes}")
    for slot, count in slot_counts.most_common(args.top):
        kind_str = ", ".join(f"{k}:{v}" for k, v in slot_kinds[slot].most_common(4))
        value_str = ", ".join(ascii(v) for v, _ in slot_values[slot].most_common(args.values))
        print(f"slot={slot} count={count} kinds=[{kind_str}] values=[{value_str}]")


if __name__ == "__main__":
    main()
