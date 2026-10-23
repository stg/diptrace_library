from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.deprecated.pre_shared_model.lib.opcode.layer1 import parse_layer1_events, read_bytes
from apps.deprecated.pre_shared_model.lib.structural.decoder import decode_structural_records


def _header7_at(data: bytes, semantic_start: int) -> str:
    return data[semantic_start : min(semantic_start + 7, len(data))].hex(" ")


def _token_at_offset(tokens: list[dict[str, Any]], offset: int) -> tuple[int, dict[str, Any]] | tuple[int, None]:
    lo = 0
    hi = len(tokens) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        token = tokens[mid]
        start = int(token["start"])
        end = int(token["end"])
        if offset < start:
            hi = mid - 1
        elif offset >= end:
            lo = mid + 1
        else:
            return mid, token
    return -1, None


def _ctx_token(tokens: list[dict[str, Any]], index: int) -> dict[str, Any]:
    if 0 <= index < len(tokens):
        return tokens[index]
    return {"kind": "", "value": None, "start": -1, "end": -1, "length": 0}


def _candidate_offsets(tokens: list[dict[str, Any]], data: bytes) -> set[int]:
    out: set[int] = set()
    n = len(data)
    for token in tokens:
        if str(token["kind"]) != "ORUN":
            continue
        start = int(token["start"])
        end = int(token["end"])
        for offset in range(start, end):
            if offset + 7 <= n and data[offset : offset + 1] == b"\x01" and data[offset + 2 : offset + 4] == b"\x0f\x42":
                out.add(offset)
    return out


def _candidate_record(
    *,
    data: bytes,
    tokens: list[dict[str, Any]],
    semantic_start: int,
    truth_offsets: set[int],
) -> dict[str, Any] | None:
    token_index, token = _token_at_offset(tokens, semantic_start)
    if token is None:
        return None
    if str(token["kind"]) != "ORUN":
        return None
    prev3 = _ctx_token(tokens, token_index - 3)
    prev2 = _ctx_token(tokens, token_index - 2)
    prev1 = _ctx_token(tokens, token_index - 1)
    next1 = _ctx_token(tokens, token_index + 1)
    next2 = _ctx_token(tokens, token_index + 2)
    next3 = _ctx_token(tokens, token_index + 3)
    prefix_byte = int(data[semantic_start - 1]) if semantic_start > 0 else -1
    trailer3 = data[max(0, semantic_start - 3) : semantic_start].hex(" ")
    intra = int(semantic_start - int(token["start"]))
    return {
        "semantic_start": int(semantic_start),
        "truth": semantic_start in truth_offsets,
        "header7_hex": _header7_at(data, semantic_start),
        "prefix_byte_hex": f"{prefix_byte:02x}" if prefix_byte >= 0 else "",
        "token_index": int(token_index),
        "orun_len": int(token["length"]),
        "intra_orun_offset": intra,
        "prev3_kind": str(prev3["kind"]),
        "prev3_value": prev3.get("value"),
        "prev2_kind": str(prev2["kind"]),
        "prev2_value": prev2.get("value"),
        "prev1_kind": str(prev1["kind"]),
        "prev1_value": prev1.get("value"),
        "next1_kind": str(next1["kind"]),
        "next1_value": next1.get("value"),
        "next2_kind": str(next2["kind"]),
        "next2_value": next2.get("value"),
        "next3_kind": str(next3["kind"]),
        "next3_value": next3.get("value"),
        "trail3prev_hex": trailer3,
        "next8_hex": data[semantic_start : min(semantic_start + 8, len(data))].hex(" "),
    }


def infer_for_file(path: Path) -> dict[str, Any]:
    data = read_bytes(path)
    tokens = [tok.as_dict() for tok in parse_layer1_events(data)]
    truth_offsets = {int(r.start) + 1 for r in decode_structural_records(data)}
    candidate_offsets = _candidate_offsets(tokens, data)
    rows: list[dict[str, Any]] = []
    for semantic_start in sorted(candidate_offsets):
        row = _candidate_record(data=data, tokens=tokens, semantic_start=semantic_start, truth_offsets=truth_offsets)
        if row is not None:
            rows.append(row)
    return {
        "file": str(path),
        "token_count": len(tokens),
        "truth_count": len(truth_offsets),
        "candidate_count": len(rows),
        "rows": rows,
    }


def _signature(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row["header7_hex"],
        row["prev3_kind"],
        row["prev2_kind"],
        row["prev1_kind"],
        row["intra_orun_offset"],
        row["next1_kind"],
        row["next2_kind"],
        row["next3_kind"],
    )


def _signature_stats(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_signature(row)].append(row)

    out: list[dict[str, Any]] = []
    for sig, items in grouped.items():
        tp = sum(1 for item in items if item["truth"])
        fp = sum(1 for item in items if not item["truth"])
        out.append(
            {
                "signature": list(sig),
                "support": len(items),
                "tp": tp,
                "fp": fp,
                "precision": (tp / len(items)) if items else 0.0,
            }
        )
    out.sort(key=lambda item: (item["fp"] > 0, -item["support"], -item["tp"]))
    return out


def _mixed_details(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_signature(row)].append(row)

    mixed: list[dict[str, Any]] = []
    for sig, items in grouped.items():
        tp = [item for item in items if item["truth"]]
        fp = [item for item in items if not item["truth"]]
        if not tp or not fp:
            continue

        def _top(items_in: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
            counts = Counter(str(item.get(key, "")) for item in items_in)
            return [{"value": value, "count": count} for value, count in counts.most_common(8)]

        mixed.append(
            {
                "signature": list(sig),
                "tp": len(tp),
                "fp": len(fp),
                "tp_prefix_top": _top(tp, "prefix_byte_hex"),
                "fp_prefix_top": _top(fp, "prefix_byte_hex"),
                "tp_prev2_value_top": _top(tp, "prev2_value"),
                "fp_prev2_value_top": _top(fp, "prev2_value"),
                "tp_prev3_value_top": _top(tp, "prev3_value"),
                "fp_prev3_value_top": _top(fp, "prev3_value"),
                "tp_prev1_value_top": _top(tp, "prev1_value"),
                "fp_prev1_value_top": _top(fp, "prev1_value"),
                "tp_trail3_top": _top(tp, "trail3prev_hex"),
                "fp_trail3_top": _top(fp, "trail3prev_hex"),
                "tp_next8_top": _top(tp, "next8_hex"),
                "fp_next8_top": _top(fp, "next8_hex"),
            }
        )

    mixed.sort(key=lambda item: (item["fp"], item["tp"]), reverse=True)
    return mixed[:limit]


def _rejected_truth_details(rows: list[dict[str, Any]], pure_signatures: set[tuple[Any, ...]], limit: int) -> list[dict[str, Any]]:
    rejected_truths = [row for row in rows if row["truth"] and not _accept_start(row, pure_signatures)]
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rejected_truths:
        grouped[_signature(row)].append(row)

    out: list[dict[str, Any]] = []
    for sig, items in grouped.items():
        def _top(key: str) -> list[dict[str, Any]]:
            counts = Counter(str(item.get(key, "")) for item in items)
            return [{"value": value, "count": count} for value, count in counts.most_common(8)]

        out.append(
            {
                "signature": list(sig),
                "count": len(items),
                "prefix_top": _top("prefix_byte_hex"),
                "prev2_value_top": _top("prev2_value"),
                "prev3_value_top": _top("prev3_value"),
                "prev1_value_top": _top("prev1_value"),
                "trail3_top": _top("trail3prev_hex"),
                "next8_top": _top("next8_hex"),
            }
        )
    out.sort(key=lambda item: item["count"], reverse=True)
    return out[:limit]


def _accept_start(row: dict[str, Any], pure_signatures: set[tuple[Any, ...]]) -> bool:
    sig = _signature(row)
    if sig in pure_signatures:
        return True

    header7 = str(row.get("header7_hex", ""))
    if (
        header7.startswith("01 00 0f 42 ")
        and header7.endswith(" 0f 42")
        and row.get("intra_orun_offset") == 0
        and row.get("next1_kind") == "ZRUN"
        and row.get("next2_kind") == "OP0F"
        and row.get("next3_kind") == "OP0F"
        and row.get("prefix_byte_hex") == "42"
        and row.get("prev1_value") == 16962
    ):
        return True

    if sig == ("01 01 0f 42 41 0f 42", "OP3B24", "OP3B24", "OP3B24", 0, "OP0F", "OP0F", "ZRUN"):
        return (
            row.get("prefix_byte_hex") == "00"
            and row.get("prev2_value") == 10144256
            and row.get("prev1_value") == 10144256
        )

    if sig == ("01 00 0f 42 40 0f 42", "OP3B24", "OP0F", "OP0F", 0, "ZRUN", "OP0F", "OP0F"):
        if row.get("prev1_value") == 16963:
            return row.get("prev3_value") == 10134256
        return row.get("prev1_value") != 16961

    if sig == ("01 01 0f 42 40 0f 42", "OP3B24", "OP0F", "OP0F", 0, "OP0F", "OP0F", "OP0F"):
        return row.get("prev1_value") not in {16961, 16963, 16984}

    if sig == ("01 01 0f 42 40 0f 42", "ZRUN", "OP0F", "OP0F", 0, "OP0F", "OP0F", "OP0F"):
        return row.get("prefix_byte_hex") == "42" and row.get("prev1_value") == 16962

    if sig == ("01 00 0f 42 40 0f 42", "OP0F", "ZRUN", "OP0F", 0, "ZRUN", "OP0F", "OP0F"):
        return row.get("prefix_byte_hex") == "42" and row.get("prev1_value") == 16962

    if sig == ("01 00 0f 42 40 0f 42", "OP3B24", "OP0F", "OP0F", 0, "ZRUN", "OP0F", "OP0F"):
        return row.get("prefix_byte_hex") == "42" and row.get("prev1_value") == 16962

    return False


def main() -> None:
    ap = argparse.ArgumentParser(description="Infer semantic layer2 token-start rules from samples.")
    ap.add_argument("--samples", required=True, help="Directory with sample .dch files")
    ap.add_argument("--root", default="", help="Optional recursive root for corpus mode")
    ap.add_argument("--workers", type=int, default=1, help="Worker count for corpus mode")
    ap.add_argument("--out", required=True, help="Output report path")
    ap.add_argument("--mixed-limit", type=int, default=24, help="Maximum mixed signatures to include")
    args = ap.parse_args()

    if args.root:
        source_dir = Path(args.root)
        files = sorted(source_dir.rglob("*.dch"))
        if args.workers > 1:
            per_file = []
            total = len(files)
            processed = 0
            last_report = time.monotonic()
            with ProcessPoolExecutor(max_workers=args.workers) as ex:
                pending = {ex.submit(infer_for_file, path): path for path in files}
                while pending:
                    done, not_done = wait(pending, timeout=1.0, return_when=FIRST_COMPLETED)
                    for fut in done:
                        path = pending.pop(fut)
                        try:
                            per_file.append(fut.result())
                        except Exception as exc:  # noqa: BLE001
                            raise RuntimeError(f"failed {path}: {exc!r}") from exc
                        processed += 1
                    now = time.monotonic()
                    if now - last_report >= 10.0 or (processed == total and processed > 0):
                        print(f"progress files={processed}/{total}")
                        last_report = now
                per_file.sort(key=lambda item: item["file"])
        else:
            per_file = [infer_for_file(path) for path in files]
    else:
        source_dir = Path(args.samples)
        files = sorted(source_dir.glob("*.dch"))
        per_file = [infer_for_file(path) for path in files]
    all_rows = [row for rep in per_file for row in rep["rows"]]
    signature_rows: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in all_rows:
        signature_rows[_signature(row)].append(row)
    pure_signatures = {
        sig
        for sig, rows in signature_rows.items()
        if rows and all(bool(row["truth"]) for row in rows)
    }
    truth_total = sum(int(rep["truth_count"]) for rep in per_file)
    candidate_total = len(all_rows)
    tp_total = sum(1 for row in all_rows if row["truth"])
    fp_total = candidate_total - tp_total
    fn_total = truth_total - tp_total
    accepted_rows = [row for row in all_rows if _accept_start(row, pure_signatures)]
    accepted_tp = sum(1 for row in accepted_rows if row["truth"])
    accepted_fp = sum(1 for row in accepted_rows if not row["truth"])
    accepted_fn = truth_total - accepted_tp

    payload = {
        "source_dir": str(source_dir),
        "file_count": len(per_file),
        "summary": {
            "truth_total": truth_total,
            "candidate_total": candidate_total,
            "tp_total": tp_total,
            "fp_total": fp_total,
            "fn_total": fn_total,
            "precision": (tp_total / candidate_total) if candidate_total else 0.0,
            "recall": (tp_total / truth_total) if truth_total else 0.0,
        },
        "accept_rule_summary": {
            "accepted_total": len(accepted_rows),
            "tp_total": accepted_tp,
            "fp_total": accepted_fp,
            "fn_total": accepted_fn,
            "precision": (accepted_tp / len(accepted_rows)) if accepted_rows else 0.0,
            "recall": (accepted_tp / truth_total) if truth_total else 0.0,
        },
        "files": [
            {
                "file": rep["file"],
                "truth_count": rep["truth_count"],
                "candidate_count": rep["candidate_count"],
                "tp": sum(1 for row in rep["rows"] if row["truth"]),
                "fp": sum(1 for row in rep["rows"] if not row["truth"]),
                "accepted": sum(1 for row in rep["rows"] if _accept_start(row, pure_signatures)),
                "accepted_tp": sum(1 for row in rep["rows"] if row["truth"] and _accept_start(row, pure_signatures)),
                "accepted_fp": sum(1 for row in rep["rows"] if (not row["truth"]) and _accept_start(row, pure_signatures)),
            }
            for rep in per_file
        ],
        "signature_stats": _signature_stats(all_rows),
        "mixed_signatures": _mixed_details(all_rows, args.mixed_limit),
        "rejected_truth_signatures": _rejected_truth_details(all_rows, pure_signatures, args.mixed_limit),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote={out} files={len(per_file)} truth={truth_total} cand={candidate_total} tp={tp_total} fp={fp_total} fn={fn_total}")


if __name__ == "__main__":
    main()
