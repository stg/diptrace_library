"""Build a component BOM from the common editable schematic model."""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.lib.design import read

_NUM_SPLIT_RE = re.compile(r"(\d+)")

def natural_key(ref: str):
    return [
        (1, int(p)) if p.isdigit() else (0, p.upper())
        for p in _NUM_SPLIT_RE.split(str(ref))
        if p
    ]

def group_bom(comps: list[dict[str, object]]) -> list[dict[str, str]]:
    # Keep first occurrence per RefDes (stable stream order).
    seen_refdes: set[str] = set()
    grouped: dict[tuple[str, str, str], set[str]] = defaultdict(set)

    for c in comps:
        ref = str(c.get("refdes", "")).strip()
        if not ref or ref in seen_refdes: continue
        seen_refdes.add(ref)
        grouped[c.get("name", ""), c.get("value", ""), c.get("pattern", "")].add(ref)

    grouped_items: list[tuple[tuple[str, str, str], list[str]]] = [
        (sig, sorted(refs, key=natural_key)) for sig, refs in grouped.items()
    ]

    grouped_items.sort(key=lambda kv: natural_key(kv[1][0]))

    return [
        {
            "RefDes": ", ".join(ref_list),
            "Name": name,
            "Value": value,
            "Pattern": pattern,
        }
        for (name, value, pattern), ref_list in grouped_items
    ]

def build_bom(path: Path) -> tuple[list[dict[str, str]], bool]:
    document = read(path)
    parts = []
    for part in document.select('/Schematic/Components/Part'):
        if part.scalar('Enabled') not in (True, 'Y') or part.scalar('PartType') != 0:
            continue
        pattern = part.child('Pattern')
        parts.append(dict(name=part.values[0], refdes=part.values[1],
                          value=part.scalar('Value', ''),
                          pattern=pattern.values[0] if pattern is not None else ''))
    return group_bom(parts), document.complete


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input_design', help='Input DCH, ASC or DCHXML schematic')
    parser.add_argument('output_csv', help='Output BOM CSV path')
    args = parser.parse_args()
    rows, _ = build_bom(Path(args.input_design))
    target = Path(args.output_csv)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('w', newline='', encoding='utf8') as output:
        writer = csv.DictWriter(output, fieldnames=['RefDes', 'Name', 'Value', 'Pattern'],
                                delimiter=';', quoting=csv.QUOTE_ALL, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    print(f'wrote={target} rows={len(rows)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
