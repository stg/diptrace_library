from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.deprecated.pre_shared_model.lib.opcode.layer1 import parse_layer1_events


def _collect_for_kind(files: list[Path], kind: str) -> dict[str, object]:
    by_val_imm_bytes: dict[int, Counter[int]] = defaultdict(Counter)
    by_val_imm_chain: dict[int, Counter[str]] = defaultdict(Counter)
    by_val_next_kind: dict[int, Counter[str]] = defaultdict(Counter)
    total = 0
    for fp in files:
        data = fp.read_bytes()
        ev = parse_layer1_events(data)
        n = len(ev)
        for i, e in enumerate(ev):
            if e.kind != kind or e.value is None:
                continue
            total += 1
            j = i + 1
            imm_bytes = 0
            chain: list[str] = []
            while j < n and ev[j].kind == "IMM_BE":
                imm_bytes += int(ev[j].end - ev[j].start)
                chain.append(str(ev[j].end - ev[j].start))
                j += 1
            by_val_imm_bytes[int(e.value)][imm_bytes] += 1
            if chain:
                by_val_imm_chain[int(e.value)]["+".join(chain)] += 1
            else:
                by_val_imm_chain[int(e.value)][""] += 1
            nk = ev[j].kind if j < n else "EOF"
            by_val_next_kind[int(e.value)][nk] += 1

    rows: list[dict[str, object]] = []
    for v in sorted(by_val_imm_bytes.keys()):
        dist = by_val_imm_bytes[v]
        seen = int(sum(dist.values()))
        top_len, top_cnt = dist.most_common(1)[0]
        row = {
            "value": int(v),
            "count": seen,
            "imm_bytes_dist": [{"bytes": int(k), "count": int(c)} for k, c in dist.most_common(8)],
            "imm_bytes_dominant": int(top_len),
            "imm_bytes_dominant_rate": round(float(top_cnt) / max(1, seen), 4),
            "imm_chain_top": [{"chain": str(k), "count": int(c)} for k, c in by_val_imm_chain[v].most_common(8)],
            "next_kind_dist": [{"kind": str(k), "count": int(c)} for k, c in by_val_next_kind[v].most_common(8)],
        }
        rows.append(row)

    stable = [
        r
        for r in rows
        if int(r["count"]) >= 20 and float(r["imm_bytes_dominant_rate"]) >= 0.97
    ]
    unstable = [r for r in rows if int(r["count"]) >= 20 and float(r["imm_bytes_dominant_rate"]) < 0.9]
    return {
        "kind": kind,
        "total": total,
        "value_count": len(rows),
        "stable_values": stable,
        "unstable_values": unstable,
        "all_values": rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Infer opcode->immediate payload behavior for layer1 tokens.")
    ap.add_argument("--samples", required=True, help="Directory with .dch files")
    ap.add_argument("--out", required=True, help="Output JSON")
    args = ap.parse_args()

    files = sorted(Path(args.samples).glob("*.dch"))
    payload = {
        "files": [str(p) for p in files],
        "op0f": _collect_for_kind(files, "OP0F"),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(
        f"wrote={out} files={len(files)} "
        f"op0f_values={payload['op0f']['value_count']}"
    )


if __name__ == "__main__":
    main()
