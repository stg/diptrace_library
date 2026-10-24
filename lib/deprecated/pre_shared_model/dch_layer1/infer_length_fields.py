from __future__ import annotations

"""Legacy local-length probe over the old framing model.

This remains useful as investigative baggage, but it operates on the earlier
frame stream, not the current clean layer1/layer2 pipeline.
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys
from typing import Callable

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.deprecated.pre_shared_model.dch_layer1.legacy_stream import build_layer1


def _u8(data: bytes, p: int) -> int | None:
    return data[p] if 0 <= p < len(data) else None


def _u16le(data: bytes, p: int) -> int | None:
    if p < 0 or p + 1 >= len(data):
        return None
    return data[p] | (data[p + 1] << 8)


def _u16be(data: bytes, p: int) -> int | None:
    if p < 0 or p + 1 >= len(data):
        return None
    return (data[p] << 8) | data[p + 1]


def _u24be(data: bytes, p: int) -> int | None:
    if p < 0 or p + 2 >= len(data):
        return None
    return (data[p] << 16) | (data[p + 1] << 8) | data[p + 2]


def _sweep_candidates(data: bytes, starts: list[int], ends: list[int], max_off: int = 64) -> list[dict[str, object]]:
    readers: list[tuple[str, Callable[[bytes, int], int | None], int]] = [
        ("u8", _u8, 1),
        ("u16le", _u16le, 2),
        ("u16be", _u16be, 2),
        ("u24be", _u24be, 3),
    ]
    best: list[dict[str, object]] = []
    for name, fn, width in readers:
        for off in range(0, max_off + 1):
            hit_exact = 0
            hit_plus = Counter()
            seen = 0
            for s, e in zip(starts, ends):
                v = fn(data, s + off)
                if v is None:
                    continue
                seen += 1
                if s + v == e:
                    hit_exact += 1
                d = e - (s + v)
                if -4096 <= d <= 4096:
                    hit_plus[d] += 1
            if seen == 0:
                continue
            best_delta, best_delta_count = (0, 0)
            if hit_plus:
                best_delta, best_delta_count = hit_plus.most_common(1)[0]
            score_exact = hit_exact / seen
            score_delta = best_delta_count / seen
            if max(score_exact, score_delta) < 0.5:
                continue
            best.append(
                {
                    "reader": name,
                    "width": width,
                    "offset": off,
                    "seen": seen,
                    "exact_hits": hit_exact,
                    "exact_rate": round(score_exact, 4),
                    "best_delta": int(best_delta),
                    "best_delta_hits": int(best_delta_count),
                    "best_delta_rate": round(score_delta, 4),
                }
            )
    best.sort(key=lambda x: (float(x["best_delta_rate"]), float(x["exact_rate"])), reverse=True)
    return best[:24]


def main() -> None:
    ap = argparse.ArgumentParser(description="Infer candidate local length fields for layer1 record starts.")
    ap.add_argument("--samples", required=True, help="Directory with .dch files")
    ap.add_argument("--out", required=True, help="Output JSON")
    args = ap.parse_args()

    files = sorted(Path(args.samples).glob("*.dch"))
    by_family: dict[str, list[tuple[bytes, int, int]]] = defaultdict(list)
    global_rows: list[tuple[bytes, int, int]] = []

    for fp in files:
        data = fp.read_bytes()
        l1 = build_layer1(data)
        for f in l1.core_frames:
            hdr = bytes([f.start_marker.b0, f.start_marker.b1, f.start_marker.b2, 0x0F, 0x42, f.start_marker.lead, f.start_marker.mode, f.start_marker.b7])
            by_family[f"core:{f.start_marker.b0:02x}:{f.start_marker.b2:02x}:{f.start_marker.lead:02x}:{f.start_marker.mode:02x}"].append((data, int(f.start), int(f.end)))
            global_rows.append((data, int(f.start), int(f.end)))
        for f in l1.extension_frames:
            by_family["extension:40:01:41:0f"].append((data, int(f.start), int(f.end)))
            global_rows.append((data, int(f.start), int(f.end)))
        for f in l1.typed_frames:
            by_family[f"typed:{f.start_marker.b0:02x}:{f.start_marker.lead:02x}"].append((data, int(f.start), int(f.end)))
            global_rows.append((data, int(f.start), int(f.end)))
        for f in l1.aux_frames:
            by_family[f"aux:{f.start_marker.b0:02x}:{f.start_marker.b2:02x}:{f.start_marker.lead:02x}:{f.start_marker.mode:02x}"].append((data, int(f.start), int(f.end)))
            global_rows.append((data, int(f.start), int(f.end)))

    fam_reports = []
    for fam, rows in sorted(by_family.items(), key=lambda kv: len(kv[1]), reverse=True):
        if len(rows) < 12:
            continue
        # grouped rows may come from multiple files; run sweep per-file and then aggregate hit candidates
        per_file: dict[int, list[tuple[int, int]]] = defaultdict(list)
        payloads: list[dict[str, object]] = []
        # naive grouping by id(data) isn't stable in json; sweep over all rows by batching contiguous same buffer references
        # Here we just split by buffer length + first bytes hash to avoid mixing unrelated files too hard.
        groups: dict[tuple[int, bytes], list[tuple[bytes, int, int]]] = defaultdict(list)
        for d, s, e in rows:
            k = (len(d), d[:32])
            groups[k].append((d, s, e))
        for (_klen, _ksig), grows in groups.items():
            d0 = grows[0][0]
            starts = [s for _d, s, _e in grows]
            ends = [e for _d, _s, e in grows]
            payloads.extend(_sweep_candidates(d0, starts, ends))
        # merge identical candidates
        merged: dict[tuple[str, int, int], dict[str, object]] = {}
        for p in payloads:
            key = (str(p["reader"]), int(p["offset"]), int(p["best_delta"]))
            cur = merged.get(key)
            if cur is None:
                merged[key] = dict(p)
            else:
                cur["seen"] = int(cur["seen"]) + int(p["seen"])
                cur["exact_hits"] = int(cur["exact_hits"]) + int(p["exact_hits"])
                cur["best_delta_hits"] = int(cur["best_delta_hits"]) + int(p["best_delta_hits"])
                cur["exact_rate"] = round(float(cur["exact_hits"]) / max(1, int(cur["seen"])), 4)
                cur["best_delta_rate"] = round(float(cur["best_delta_hits"]) / max(1, int(cur["seen"])), 4)
        top = sorted(merged.values(), key=lambda x: (float(x["best_delta_rate"]), float(x["exact_rate"])), reverse=True)[:12]
        fam_reports.append({"family": fam, "count": len(rows), "candidates": top})

    out = {
        "files": [str(p) for p in files],
        "family_count": len(fam_reports),
        "families": fam_reports,
    }
    op = Path(args.out)
    op.parent.mkdir(parents=True, exist_ok=True)
    op.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote={op} families={len(fam_reports)}")


if __name__ == "__main__":
    main()
