from __future__ import annotations

import argparse
import bisect
import json
from collections import Counter
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.deprecated.pre_shared_model.lib.opcode.layer1 import read_bytes, tokenize_opcode_layer as tokenize_layer1
from apps.deprecated.pre_shared_model.lib.structural.decoder import decode_structural_records


def _token_windows(tokens: list[dict[str, Any]], starts: list[int], width: int = 8) -> Counter[str]:
    starts_only = [int(t["start"]) for t in tokens]
    out: Counter[str] = Counter()
    for s in starts:
        i = bisect.bisect_left(starts_only, int(s))
        if i >= len(tokens):
            continue
        if int(tokens[i]["start"]) != int(s):
            continue
        seq = []
        for j in range(i, min(i + width, len(tokens))):
            t = tokens[j]
            label = str(t["kind"])
            if "value" in t:
                label += f":{int(t['value'])}"
            else:
                label += f":len{int(t.get('len', 0))}"
            seq.append(label)
        out[" | ".join(seq)] += 1
    return out


def _token_kind_counts(tokens: list[dict[str, Any]]) -> dict[str, int]:
    c: Counter[str] = Counter()
    for t in tokens:
        c[str(t["kind"])] += 1
    return dict(sorted(c.items(), key=lambda kv: (-kv[1], kv[0])))


def analyze_file(path: Path) -> dict[str, Any]:
    data = read_bytes(path)
    toks = [t.as_dict() for t in tokenize_layer1(data)]
    recs = decode_structural_records(data)

    token_starts = {int(t["start"]) for t in toks}
    rec_starts = [int(r.start) for r in recs]
    aligned = sum(1 for s in rec_starts if s in token_starts)

    # Start-shape in raw bytes (first 8 bytes at structural starts).
    start_prefix8: Counter[str] = Counter()
    for s in rec_starts:
        start_prefix8[data[s : s + 8].hex(" ")] += 1

    # Token windows at structural starts.
    win = _token_windows(toks, rec_starts, width=8)

    # Candidate "false-long" records: top by span/consumed gap.
    decoded = []
    for r in recs:
        decoded.append(
            {
                "start": int(r.start),
                "end": int(r.end),
                "len": int(r.length),
                "lead": int(r.lead),
                "mode": int(r.mode),
            }
        )
    decoded.sort(key=lambda x: x["len"], reverse=True)

    return {
        "file": str(path),
        "size": len(data),
        "token_count": len(toks),
        "token_kind_counts": _token_kind_counts(toks),
        "structural_record_count": len(recs),
        "structural_starts_aligned_to_token_start": aligned,
        "structural_start_align_rate": float(aligned / len(recs)) if recs else 1.0,
        "structural_start_prefix8_top": [{"prefix8": k, "count": v} for k, v in start_prefix8.most_common(16)],
        "structural_start_token_window_top": [{"window": k, "count": v} for k, v in win.most_common(12)],
        "longest_structural_records": decoded[:12],
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Analyze first-layer token grammar and alignment with current structural starts."
    )
    ap.add_argument("--samples", required=True, help="Directory with .dch files")
    ap.add_argument("--out", required=True, help="Output JSON report")
    args = ap.parse_args()

    sample_dir = Path(args.samples)
    files = sorted(sample_dir.glob("*.dch"))
    reports: list[dict[str, Any]] = []
    for fp in files:
        reports.append(analyze_file(fp))

    # Global aggregates.
    global_kind: Counter[str] = Counter()
    global_prefix: Counter[str] = Counter()
    global_window: Counter[str] = Counter()
    total_records = 0
    total_aligned = 0
    for r in reports:
        for k, v in r["token_kind_counts"].items():
            global_kind[str(k)] += int(v)
        for it in r["structural_start_prefix8_top"]:
            global_prefix[str(it["prefix8"])] += int(it["count"])
        for it in r["structural_start_token_window_top"]:
            global_window[str(it["window"])] += int(it["count"])
        total_records += int(r["structural_record_count"])
        total_aligned += int(r["structural_starts_aligned_to_token_start"])

    payload = {
        "samples_dir": str(sample_dir),
        "file_count": len(reports),
        "files": reports,
        "global": {
            "token_kind_counts": dict(sorted(global_kind.items(), key=lambda kv: (-kv[1], kv[0]))),
            "structural_records_total": total_records,
            "structural_starts_aligned_to_token_start_total": total_aligned,
            "structural_start_align_rate_total": float(total_aligned / total_records) if total_records else 1.0,
            "structural_start_prefix8_top": [{"prefix8": k, "count": v} for k, v in global_prefix.most_common(20)],
            "structural_start_token_window_top": [{"window": k, "count": v} for k, v in global_window.most_common(20)],
        },
    }
    total_start_windows = sum(global_window.values())
    top5 = sum(v for _k, v in global_window.most_common(5))
    top10 = sum(v for _k, v in global_window.most_common(10))
    payload["global"]["start_window_coverage"] = {
        "total": int(total_start_windows),
        "top5_count": int(top5),
        "top5_rate": float(top5 / total_start_windows) if total_start_windows else 0.0,
        "top10_count": int(top10),
        "top10_rate": float(top10 / total_start_windows) if total_start_windows else 0.0,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(
        f"wrote={out} files={len(reports)} "
        f"records={total_records} aligned={total_aligned} "
        f"rate={payload['global']['structural_start_align_rate_total']:.6f}"
    )


if __name__ == "__main__":
    main()
