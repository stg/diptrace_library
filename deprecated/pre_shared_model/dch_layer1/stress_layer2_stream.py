from __future__ import annotations

import argparse
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.deprecated.pre_shared_model.lib.structural.decoder import decode_structural_records, read_bytes


def _tail(header8: bytes) -> str:
    return f"{header8[6]:02x} {header8[7]:02x}" if len(header8) >= 8 else ""


def _header7(header8: bytes) -> str:
    return header8[1:8].hex(" ") if len(header8) >= 8 else ""


def _scan_file(path: Path) -> dict[str, object]:
    data = read_bytes(path)
    records = decode_structural_records(data)

    header_counts: Counter[str] = Counter()
    header7_counts: Counter[str] = Counter()
    prefix_by_header7: dict[str, Counter[str]] = {}
    tail_counts: Counter[str] = Counter()
    gap_counts: Counter[int] = Counter()
    transition_counts: Counter[str] = Counter()

    for i, rec in enumerate(records):
        header = data[rec.start : min(rec.start + 8, len(data))]
        header_hex = header.hex(" ")
        header_counts[header_hex] += 1
        header7_hex = _header7(header)
        header7_counts[header7_hex] += 1
        prefix_by_header7.setdefault(header7_hex, Counter())[f"{header[0]:02x}"] += 1
        tail_counts[_tail(header)] += 1
        if i + 1 < len(records):
            next_header = data[records[i + 1].start : min(records[i + 1].start + 8, len(data))]
            gap_counts[int(records[i + 1].start - rec.end)] += 1
            transition_counts[f"{header_hex} -> {next_header.hex(' ')}"] += 1

    return {
        "file": str(path),
        "record_count": len(records),
        "header_counts": dict(header_counts),
        "header7_counts": dict(header7_counts),
        "prefix_by_header7": {k: dict(v) for k, v in prefix_by_header7.items()},
        "tail_counts": dict(tail_counts),
        "gap_counts": {str(k): int(v) for k, v in gap_counts.items()},
        "transition_counts": dict(transition_counts),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Stress-test layer2 record-stream structure across many DCH files.")
    ap.add_argument("--root", required=True, help="Root directory to scan for .dch files")
    ap.add_argument("--workers", type=int, default=8, help="Worker count")
    ap.add_argument("--out", required=True, help="Output JSON file")
    args = ap.parse_args()

    files = sorted(Path(args.root).rglob("*.dch"))
    header_counts: Counter[str] = Counter()
    header7_counts: Counter[str] = Counter()
    prefix_by_header7: dict[str, Counter[str]] = {}
    tail_counts: Counter[str] = Counter()
    gap_counts: Counter[str] = Counter()
    transition_counts: Counter[str] = Counter()
    failures: list[dict[str, str]] = []

    with ThreadPoolExecutor(max_workers=max(1, int(args.workers))) as ex:
        futures = {ex.submit(_scan_file, fp): fp for fp in files}
        done = 0
        for fut in as_completed(futures):
            fp = futures[fut]
            done += 1
            try:
                rep = fut.result()
                header_counts.update(rep["header_counts"])
                header7_counts.update(rep["header7_counts"])
                for key, counts in rep["prefix_by_header7"].items():
                    prefix_by_header7.setdefault(key, Counter()).update(counts)
                tail_counts.update(rep["tail_counts"])
                gap_counts.update(rep["gap_counts"])
                transition_counts.update(rep["transition_counts"])
            except Exception as exc:
                failures.append({"file": str(fp), "error": str(exc)})
            if done % 100 == 0 or done == len(files):
                print(f"files={done}/{len(files)} failed={len(failures)}")

    payload = {
        "root": str(Path(args.root)),
        "file_count": len(files),
        "failure_count": len(failures),
        "files_failed": failures,
        "summary": {
            "record_total": int(sum(header_counts.values())),
            "transition_total": int(sum(transition_counts.values())),
            "distinct_headers": len(header_counts),
            "distinct_tails": len(tail_counts),
        },
        "header_counts_top": [{"header8_hex": k, "count": v} for k, v in header_counts.most_common(64)],
        "header7_counts_top": [{"header7_hex": k, "count": v} for k, v in header7_counts.most_common(64)],
        "prefix_by_header7_top": [
            {
                "header7_hex": key,
                "count": int(header7_counts[key]),
                "prefix_counts": dict(sorted(counts.items(), key=lambda item: item[1], reverse=True)[:16]),
            }
            for key, counts in sorted(prefix_by_header7.items(), key=lambda item: header7_counts[item[0]], reverse=True)[:64]
        ],
        "tail_counts": dict(tail_counts),
        "gap_counts": dict(gap_counts),
        "transition_counts_top": [{"transition": k, "count": v} for k, v in transition_counts.most_common(128)],
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(
        f"wrote={out} files={len(files)} failures={len(failures)} "
        f"records={payload['summary']['record_total']} transitions={payload['summary']['transition_total']}"
    )


if __name__ == "__main__":
    main()
