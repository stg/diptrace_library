from __future__ import annotations

"""Legacy export of the old framing stream model.

This script is exploratory baggage retained for reproducing earlier findings.
The live opcode path no longer consumes this exported stream format.
"""

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.deprecated.pre_shared_model.dch_layer1.layer1_stream import build_layer1_records, classify_start_family, detect_start_candidates
from lib.deprecated.pre_shared_model.dch_layer1.layer1_tokenizer import read_bytes
from lib.deprecated.pre_shared_model.lib.structural.decoder import StructuralRecord, _decode_one_record, classify_family, decode_structural_records


def _decode_type(data: bytes, start: int, end: int, idx: int) -> str:
    if not (0 <= start < end <= len(data)):
        return ""
    lead = int(data[start + 5]) if start + 5 < len(data) else -1
    mode = int(data[start + 6]) if start + 6 < len(data) else -1
    rr = StructuralRecord(
        index=int(idx),
        start=int(start),
        end=int(end),
        length=int(end - start),
        lead=int(lead),
        mode=int(mode),
        family=classify_family(int(mode)),
        group=0,
    )
    d = _decode_one_record(data, rr)
    if not isinstance(d, dict):
        return ""
    return str(d.get("RecordType", ""))


def _depth_hint(prev: dict[str, Any] | None, cur: dict[str, Any]) -> str:
    if prev is None:
        return "root"
    try:
        pmode = int(prev["header"]["mode"])
        pb2 = int(prev["header"]["b2"])
        cmode = int(cur["header"]["mode"])
        clead = int(cur["header"]["lead"])
    except Exception:
        return "sibling"
    if pmode == 0x0F and pb2 == 0x00 and cmode == 0x01 and clead == 0x41:
        return "child_of_prev"
    if pmode == 0x0F and pb2 == 0x01 and cmode == 0x00 and clead == 0x46:
        return "child_of_prev"
    return "sibling"


PROBE_MARKERS: list[tuple[str, bytes]] = [
    ("alt_0142413b", bytes.fromhex("01 0f 42 41 3b")),
    ("show_tuple", bytes.fromhex("01 0f 42 41 0f 44 fc")),
    ("pattern_40", bytes.fromhex("0f 42 40 00")),
    ("pattern_41", bytes.fromhex("0f 42 41 00")),
    ("block_0f4273_01000000", bytes.fromhex("0f 42 73 01 00 00 00")),
]


def _probe_markers(data: bytes, start: int, end: int, limit_each: int = 12) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for name, pat in PROBE_MARKERS:
        hits: list[int] = []
        i = start
        while len(hits) < limit_each:
            j = data.find(pat, i, end)
            if j < 0:
                break
            hits.append(int(j))
            i = j + 1
        if hits:
            out[name] = hits
    return out


def export_stream_for_file(path: Path) -> dict[str, Any]:
    data = read_bytes(path)
    cands = detect_start_candidates(data)
    recs = build_layer1_records(data, cands)
    old = decode_structural_records(data)
    old_starts = {int(r.start) for r in old}

    out_records: list[dict[str, Any]] = []
    for i, r in enumerate(recs):
        dt = _decode_type(data, r.start, r.end, i)
        shared = int(r.start) in old_starts
        if shared:
            tier = "core"
            conf = 1.0
        elif dt in ("TokenContainer", "TokenNamed", "CacheEntry", "Pattern"):
            tier = "extension"
            conf = 0.8
        else:
            tier = "uncertain"
            conf = 0.5
        row = {
            "index": int(i),
            "start": int(r.start),
            "end": int(r.end),
            "length": int(r.length),
            "tier": tier,
            "confidence": conf,
            "shared_with_structural": shared,
            "decoded_type_hint": dt,
            "start_family": classify_start_family(r.candidate),
            "header": {
                "b0": int(r.candidate.b0),
                "b1": int(r.candidate.b1),
                "b2": int(r.candidate.b2),
                "lead": int(r.candidate.lead),
                "mode": int(r.candidate.mode),
                "b7": int(r.candidate.b7),
                "start8_hex": r.candidate.as_dict()["start8_hex"],
            },
        }
        out_records.append(row)

    prev: dict[str, Any] | None = None
    for r in out_records:
        r["depth_hint"] = _depth_hint(prev, r)
        if int(r["length"]) >= 4096:
            r["probe_markers"] = _probe_markers(data, int(r["start"]), int(r["end"]))
        prev = r

    return {
        "file": str(path),
        "size": len(data),
        "record_count": len(out_records),
        "records": out_records,
        "summary": {
            "core": sum(1 for r in out_records if r["tier"] == "core"),
            "extension": sum(1 for r in out_records if r["tier"] == "extension"),
            "uncertain": sum(1 for r in out_records if r["tier"] == "uncertain"),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Export layer1 frame stream for second-layer parser input.")
    ap.add_argument("--samples", required=True, help="Directory with .dch files")
    ap.add_argument("--out-dir", required=True, help="Output directory")
    args = ap.parse_args()

    sdir = Path(args.samples)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(sdir.glob("*.dch"))
    manifest: list[dict[str, Any]] = []
    for fp in files:
        stream = export_stream_for_file(fp)
        out_path = out_dir / f"{fp.stem}.layer1.stream.json"
        out_path.write_text(json.dumps(stream, indent=2), encoding="utf-8")
        manifest.append(
            {
                "file": str(fp),
                "stream_file": str(out_path),
                "record_count": int(stream["record_count"]),
                "summary": stream["summary"],
            }
        )
    mpath = out_dir / "manifest.json"
    mpath.write_text(json.dumps({"count": len(manifest), "files": manifest}, indent=2), encoding="utf-8")
    total = sum(int(x["record_count"]) for x in manifest)
    print(f"wrote={out_dir} files={len(manifest)} records={total}")


if __name__ == "__main__":
    main()
