from __future__ import annotations

"""Compare binary root sections to ASC top-level section counts.

ASC section counting uses indentation:
- a top-level section starts at a line beginning with exactly two spaces
  followed by `(` and the section name
- the section ends at a line exactly equal to `  )`
- the section's immediate item count is the number of lines between start/end
  that begin with exactly four spaces followed by `(`
"""

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.deprecated.pre_shared_model.lib.opcode import decode_opcode_structure_tree


@dataclass(frozen=True)
class AscSectionCount:
    name: str
    count: int


def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def _count_asc_section(lines: list[str], section_name: str) -> int | None:
    start = None
    needle = f"  ({section_name}"
    for i, line in enumerate(lines):
        if line.startswith(needle):
            start = i
            break
    if start is None:
        return None
    end = None
    for j in range(start + 1, len(lines)):
        if lines[j] == "  )":
            end = j
            break
    if end is None:
        return None
    return sum(1 for line in lines[start + 1 : end] if line.startswith("    ("))


def _asc_counts(path: Path, section_names: list[str]) -> list[AscSectionCount]:
    lines = _read_lines(path)
    out: list[AscSectionCount] = []
    for name in section_names:
        count = _count_asc_section(lines, name)
        if count is not None:
            out.append(AscSectionCount(name=name, count=int(count)))
    return out


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Compare ASC section counts to binary root sections.")
    ap.add_argument("inputs", nargs="+", help="Input .dch files")
    ap.add_argument(
        "--sections",
        nargs="*",
        default=[
            "Components",
            "PageConnectors",
            "Shapes",
            "Nets",
            "Buses",
            "Groups",
            "Tables",
            "Settings",
            "CacheLib",
        ],
        help="ASC top-level sections to count",
    )
    return ap


def main() -> int:
    args = build_parser().parse_args()
    for item in args.inputs:
        dch_path = Path(item)
        asc_path = dch_path.with_suffix(".asc")
        print(dch_path.name)
        if not asc_path.exists():
            print("  asc: missing")
            continue
        _tokens, _stream, tree = decode_opcode_structure_tree(dch_path)
        for sec in _asc_counts(asc_path, list(args.sections)):
            print(f"  asc {sec.name:<14} count={sec.count}")
        print("  root_sections")
        for sec in tree.iter_root_sections():
            print(
                "   "
                f"idx={sec.section_index:<3d} "
                f"sig={sec.signature_hex} "
                f"run={sec.run_length}"
            )
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
