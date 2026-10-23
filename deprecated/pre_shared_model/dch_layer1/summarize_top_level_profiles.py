from __future__ import annotations

"""Summarize top-level binary root profiles against ASC section counts.

This is an analysis tool only. It does not infer semantic section names from
payload text. It uses ASC counts as external alignment truth and reports which
binary root profiles occur inside each aligned top-level section.
"""

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.deprecated.pre_shared_model.lib.opcode import decode_opcode_structure_tree


SECTIONS = ("Components", "PageConnectors", "Shapes", "Nets", "Buses", "Groups", "Tables", "Settings", "CacheLib")


def _asc_section_count(lines: list[str], section_name: str) -> int:
    start = next((i for i, line in enumerate(lines) if line.startswith(f"  ({section_name}")), None)
    if start is None:
        return 0
    end = next((j for j in range(start + 1, len(lines)) if lines[j] == "  )"), None)
    if end is None:
        return 0
    return sum(1 for line in lines[start + 1 : end] if line.startswith("    ("))


def _profile_bucket(atom_count: int) -> str:
    if atom_count <= 30:
        return "short<=30"
    if atom_count <= 80:
        return "mid<=80"
    if atom_count <= 250:
        return "long<=250"
    return "xlong>250"


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Summarize top-level root profiles aligned to ASC section counts.")
    ap.add_argument("inputs", nargs="+", help="Input .dch files")
    return ap


def main() -> int:
    args = build_parser().parse_args()
    aggregate: dict[str, Counter[tuple[str, int, bool]]] = defaultdict(Counter)
    aggregate_exact: dict[str, Counter[tuple[str, int, int, bool]]] = defaultdict(Counter)

    for item in args.inputs:
        dch_path = Path(item)
        asc_path = dch_path.with_suffix(".asc")
        if not asc_path.exists():
            continue
        lines = asc_path.read_text(encoding="utf-8", errors="replace").splitlines()
        counts = [(_name, _asc_section_count(lines, _name)) for _name in SECTIONS]
        _tokens, _stream, tree = decode_opcode_structure_tree(dch_path)
        roots = list(tree.roots)
        off = 0
        print(dch_path.name)
        for section_name, count in counts:
            segment = roots[off : off + count]
            print(f"  {section_name:<14} count={count}")
            local = Counter(
                (
                    _profile_bucket(len(root.token_slices)),
                    len(root.children),
                    bool(root.embedded_children),
                )
                for root in segment
            )
            for (bucket, child_count, has_embedded), n in local.most_common(8):
                print(f"    {n:4d} bucket={bucket:<10} children={child_count} embedded={int(has_embedded)}")
            for root in segment:
                aggregate[section_name][
                    (
                        _profile_bucket(len(root.token_slices)),
                        len(root.children),
                        bool(root.embedded_children),
                    )
                ] += 1
                aggregate_exact[section_name][
                    (
                        str(root.record.signature_hex),
                        len(root.token_slices),
                        len(root.children),
                        bool(root.embedded_children),
                    )
                ] += 1
            off += count
        print()

    print("aggregate")
    for section_name in SECTIONS:
        print(f"  {section_name}")
        for (bucket, child_count, has_embedded), n in aggregate[section_name].most_common(10):
            print(f"    {n:4d} bucket={bucket:<10} children={child_count} embedded={int(has_embedded)}")
        print("    exact")
        for (sig, atom_count, child_count, has_embedded), n in aggregate_exact[section_name].most_common(10):
            print(
                f"      {n:4d} sig={sig} atoms={atom_count} "
                f"children={child_count} embedded={int(has_embedded)}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
