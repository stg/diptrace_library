from __future__ import annotations

"""Legacy framing analysis based on the old start-candidate stream model.

This script is kept for historical comparison only. It does not describe the
current live opcode pipeline.
"""

import argparse
import json
from collections import Counter
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.deprecated.pre_shared_model.dch_layer1.layer1_stream import build_layer1_records, classify_start_family, detect_start_candidates
from lib.deprecated.pre_shared_model.dch_layer1.layer1_tokenizer import read_bytes, tokenize_layer1
from lib.deprecated.pre_shared_model.lib.structural.decoder import StructuralRecord, _decode_one_record, classify_family, decode_structural_records


def _first_tokens(tokens: list[dict[str, Any]], start: int, n: int = 10) -> list[dict[str, Any]]:
    i = 0
    while i < len(tokens) and int(tokens[i]["start"]) < int(start):
        i += 1
    if i >= len(tokens) or int(tokens[i]["start"]) != int(start):
        return []
    return tokens[i : i + n]


def analyze_file(path: Path) -> dict[str, Any]:
    data = read_bytes(path)
    toks = [t.as_dict() for t in tokenize_layer1(data)]
    cands = detect_start_candidates(data)
    recs = build_layer1_records(data, cands)
    old = decode_structural_records(data)
    old_starts = {int(r.start) for r in old}
    new_starts = {int(r.start) for r in recs}

    only_new = sorted(new_starts - old_starts)
    only_old = sorted(old_starts - new_starts)

    def _decode_l1_record(rstart: int, rend: int, idx: int) -> str:
        if not (0 <= rstart < rend <= len(data)):
            return ""
        lead = int(data[rstart + 5]) if rstart + 5 < len(data) else -1
        mode = int(data[rstart + 6]) if rstart + 6 < len(data) else -1
        rr = StructuralRecord(
            index=int(idx),
            start=int(rstart),
            end=int(rend),
            length=int(rend - rstart),
            lead=int(lead),
            mode=int(mode),
            family=classify_family(int(mode)),
            group=0,
        )
        d = _decode_one_record(data, rr)
        if not isinstance(d, dict):
            return ""
        return str(d.get("RecordType", ""))

    b0_counter: Counter[int] = Counter()
    fam_counter: Counter[str] = Counter()
    lead_mode_counter: Counter[str] = Counter()
    for c in cands:
        if int(c.score) < 8:
            continue
        b0_counter[int(c.b0)] += 1
        fam_counter[classify_start_family(c)] += 1
        lead_mode_counter[f"lead={c.lead:02x},mode={c.mode:02x},b2={c.b2:02x},b7={c.b7:02x}"] += 1

    long_new = sorted(recs, key=lambda r: r.length, reverse=True)[:20]
    l1_decode_counts_all: Counter[str] = Counter()
    l1_decode_counts_only_new: Counter[str] = Counter()
    l1_decode_counts_shared: Counter[str] = Counter()
    l1_decoded_rows: list[dict[str, Any]] = []
    for r in recs:
        dt = _decode_l1_record(r.start, r.end, r.index)
        key = dt if dt else "(none)"
        l1_decode_counts_all[key] += 1
        if r.start in old_starts:
            l1_decode_counts_shared[key] += 1
        else:
            l1_decode_counts_only_new[key] += 1
        if len(l1_decoded_rows) < 40:
            l1_decoded_rows.append(
                {
                    "start": int(r.start),
                    "end": int(r.end),
                    "length": int(r.length),
                    "decoded_type": key,
                    "shared_start": bool(r.start in old_starts),
                    "header": r.start_marker.as_dict(),
                }
            )

    long_with_internal = []
    for r in long_new:
        inside = [c for c in cands if int(c.score) >= 8 and r.start < c.offset < r.end]
        if inside:
            long_with_internal.append(
                {
                    "start": r.start,
                    "end": r.end,
                    "length": r.length,
                    "internal_strong_count": len(inside),
                    "internal_first_offsets": [int(c.offset) for c in inside[:8]],
                    "start_header": r.start_marker.as_dict(),
                    "start_tokens": _first_tokens(toks, r.start, n=8),
                }
            )

    return {
        "file": str(path),
        "size": len(data),
        "token_count": len(toks),
        "candidate_count": len(cands),
        "strong_candidate_count": sum(1 for c in cands if int(c.score) >= 8),
        "layer1_record_count": len(recs),
        "structural_record_count": len(old),
        "shared_start_count": len(new_starts & old_starts),
        "only_new_start_count": len(only_new),
        "only_old_start_count": len(only_old),
        "only_new_start_sample": only_new[:30],
        "only_old_start_sample": only_old[:30],
        "strong_b0_top": [{"b0": k, "hex": f"{k:02x}", "count": v} for k, v in b0_counter.most_common(16)],
        "strong_family_counts": [{"family": k, "count": v} for k, v in fam_counter.most_common(12)],
        "strong_header_tuple_top": [{"tuple": k, "count": v} for k, v in lead_mode_counter.most_common(20)],
        "l1_decode_type_counts_all": [{"type": k, "count": v} for k, v in l1_decode_counts_all.most_common(20)],
        "l1_decode_type_counts_shared_starts": [{"type": k, "count": v} for k, v in l1_decode_counts_shared.most_common(20)],
        "l1_decode_type_counts_only_new_starts": [{"type": k, "count": v} for k, v in l1_decode_counts_only_new.most_common(20)],
        "l1_decoded_rows_sample": l1_decoded_rows,
        "longest_records": [
            {
                "start": int(r.start),
                "end": int(r.end),
                "length": int(r.length),
                "header": r.start_marker.as_dict(),
                "start_tokens": _first_tokens(toks, r.start, n=8),
            }
            for r in long_new
        ],
        "long_records_with_internal_strong_starts": long_with_internal,
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Build first-layer record stream and compare against current structural starts."
    )
    ap.add_argument("--samples", required=True, help="Directory with .dch files")
    ap.add_argument("--out", required=True, help="Output JSON")
    args = ap.parse_args()

    sdir = Path(args.samples)
    files = sorted(sdir.glob("*.dch"))
    reports = [analyze_file(fp) for fp in files]

    payload = {
        "samples_dir": str(sdir),
        "file_count": len(reports),
        "files": reports,
        "summary": {
            "layer1_records_total": sum(int(r["layer1_record_count"]) for r in reports),
            "structural_records_total": sum(int(r["structural_record_count"]) for r in reports),
            "shared_start_total": sum(int(r["shared_start_count"]) for r in reports),
            "only_new_start_total": sum(int(r["only_new_start_count"]) for r in reports),
            "only_old_start_total": sum(int(r["only_old_start_count"]) for r in reports),
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    s = payload["summary"]
    print(
        f"wrote={out} files={len(reports)} "
        f"layer1={s['layer1_records_total']} structural={s['structural_records_total']} "
        f"shared={s['shared_start_total']} only_new={s['only_new_start_total']}"
    )


if __name__ == "__main__":
    main()
