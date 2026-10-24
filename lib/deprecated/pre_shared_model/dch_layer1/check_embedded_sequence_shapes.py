from __future__ import annotations

"""Check an older narrow two-family embedded-sequence hypothesis.

This script only tests the historical `show* pattern*` subset. It is useful
for comparing the old two-family extractor against the newer broader embedded
grammar, but it is no longer the full structural claim for layer3.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.deprecated.pre_shared_model.lib.opcode import decode_opcode_structure_tree


SHOW = "OpcodeEmbedded[ORUN,OP0F,OP0F44FC,OP0F,ZRUN,OP0F,TEXT,TEXT]"
PATTERN = "OpcodeEmbedded[ORUN,OP3B24,OP3B24,OP0F,TEXT]"
TARGET_SIGNATURES = {
    "01 00 0f 42 40 0f 42",
    "01 00 0f 42 42 0f 42",
    "01 00 0f 42 41 01 0f",
    "01 00 0f 42 41 0f 42",
    "01 00 0f 42 42 01 0f",
}


def _is_show_star_pattern_star(seq: tuple[str, ...]) -> bool:
    i = 0
    while i < len(seq) and seq[i] == SHOW:
        i += 1
    while i < len(seq) and seq[i] == PATTERN:
        i += 1
    return i == len(seq)


def _worker(path_str: str) -> dict:
    _tokens, _stream, tree = decode_opcode_structure_tree(path_str)
    checked = 0
    bad: list[dict] = []
    counts_by_signature: dict[str, dict[str, int]] = {}
    for node in tree.iter_nodes():
        sig = str(node.record.signature_hex)
        if sig not in TARGET_SIGNATURES:
            continue
        seq = tuple(str(emb.structure_type) for emb in node.embedded_children)
        checked += 1
        show_count = sum(1 for x in seq if x == SHOW)
        pattern_count = sum(1 for x in seq if x == PATTERN)
        entry = counts_by_signature.setdefault(sig, {"records": 0, "show_max": 0, "pattern_max": 0})
        entry["records"] += 1
        entry["show_max"] = max(int(entry["show_max"]), int(show_count))
        entry["pattern_max"] = max(int(entry["pattern_max"]), int(pattern_count))
        if not _is_show_star_pattern_star(seq):
            bad.append(
                {
                    "file": str(path_str),
                    "signature": sig,
                    "record_index": int(node.record.index),
                    "sequence": list(seq),
                }
            )
    return {"checked": checked, "bad": bad, "counts_by_signature": counts_by_signature}


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Check embedded sequence regularity on a DCH corpus.")
    ap.add_argument("--root", required=True, help="Root directory to search for .dch files")
    ap.add_argument("--workers", type=int, default=8, help="Number of worker processes")
    ap.add_argument("--progress-sec", type=float, default=10.0, help="Progress print interval")
    return ap


def main() -> int:
    args = build_parser().parse_args()
    files = sorted(Path(args.root).rglob("*.dch"))
    checked = 0
    bad: list[dict] = []
    counts_by_signature: dict[str, dict[str, int]] = {}
    t0 = time.time()
    last = t0

    with ProcessPoolExecutor(max_workers=int(args.workers)) as ex:
        futures = [ex.submit(_worker, str(path)) for path in files]
        for i, fut in enumerate(as_completed(futures), 1):
            res = fut.result()
            checked += int(res["checked"])
            bad.extend(list(res["bad"]))
            for sig, entry in res["counts_by_signature"].items():
                cur = counts_by_signature.setdefault(sig, {"records": 0, "show_max": 0, "pattern_max": 0})
                cur["records"] += int(entry["records"])
                cur["show_max"] = max(int(cur["show_max"]), int(entry["show_max"]))
                cur["pattern_max"] = max(int(cur["pattern_max"]), int(entry["pattern_max"]))
            now = time.time()
            if now - last >= float(args.progress_sec) or i == len(futures):
                print(f"progress files={i}/{len(futures)} checked={checked} bad={len(bad)} elapsed={now - t0:.1f}s")
                last = now

    print(f"summary checked={checked} bad={len(bad)}")
    for sig, entry in sorted(counts_by_signature.items()):
        print(
            f"signature={sig} records={entry['records']} "
            f"show_max={entry['show_max']} pattern_max={entry['pattern_max']}"
        )
    for row in bad[:20]:
        print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
