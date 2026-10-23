from __future__ import annotations

"""Inspect one outer Part-like opcode record structurally.

This tool is intentionally structural-first:
- partition the record into local ORUN-led segments
- show which segments are already recognized by the embedded grammar
- optionally print the paired ASC subtree only as external validation
"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.deprecated.pre_shared_model.lib.opcode import decode_opcode_structure_tree


def _extract_first_part_asc(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line.startswith("    (Part "):
            start = idx
            break
    if start is None:
        return []
    out: list[str] = []
    for idx in range(start, len(lines)):
        line = lines[idx]
        out.append(f"{idx + 1:04d}: {line}")
        if idx > start and line.strip() == ")" and (len(line) - len(line.lstrip(" "))) == 4:
            break
    return out


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Inspect one outer Part record structurally.")
    ap.add_argument("dch", help="Input .dch file")
    ap.add_argument("--root-index", type=int, default=0, help="Root record index inside the file")
    ap.add_argument("--asc", default="", help="Optional paired .asc file for external validation output")
    ap.add_argument("--tokens", action="store_true", help="Print tokens for each local segment")
    return ap


def main() -> int:
    args = build_parser().parse_args()
    tokens, stream, tree = decode_opcode_structure_tree(Path(args.dch))
    if args.root_index < 0 or args.root_index >= len(tree.roots):
        raise SystemExit(f"root index out of range: {args.root_index}")
    root = tree.roots[int(args.root_index)]

    print(f"root_index={args.root_index}")
    print(f"signature={root.record.signature_hex}")
    print(f"record_index={root.record.index}")
    print(f"atom_count={len(root.token_slices)}")
    print(f"local_segment_count={len(root.local_segments)}")
    print(f"embedded_count={len(root.embedded_children)}")
    print()

    for idx, seg in enumerate(root.local_segments):
        texts = [tok.text for tok in seg.token_slices if tok.text is not None]
        local_code = None
        if len(seg.token_slices) > 1 and seg.token_slices[1].kind == "OP0F" and seg.token_slices[1].value is not None:
            local_code = int(seg.token_slices[1].value) - 0x4240
        print(
            f"segment[{idx}] atoms={seg.start_atom}-{seg.end_atom} "
            f"count={seg.end_atom - seg.start_atom + 1} "
            f"recognized={seg.recognized_structure_type!r} "
            f"local_code={local_code!r} "
            f"texts={texts!r}"
        )
        prefix = [(tok.kind, None if tok.text is not None else tok.value) for tok in seg.token_slices[:8]]
        print(f"  prefix={prefix}")
        if args.tokens:
            for atom_idx, tok in enumerate(seg.token_slices, start=seg.start_atom):
                print(f"    {atom_idx:03d} {tok.kind:20s} value={tok.value!s:8s} text={tok.text!r}")

    if args.asc:
        asc_lines = _extract_first_part_asc(Path(args.asc))
        if asc_lines:
            print()
            print("ASC first Part subtree")
            for line in asc_lines:
                print(line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
