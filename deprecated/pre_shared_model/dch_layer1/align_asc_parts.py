from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.deprecated.pre_shared_model.dch_layer1.infer_layer1_grammar import _first_n_keys
from apps.deprecated.pre_shared_model.lib.opcode.layer1 import tokenize_opcode_layer as tokenize_layer1
from apps.deprecated.pre_shared_model.lib.structural.decoder import decode_structural_components, read_bytes
from apps.deprecated.pre_shared_model.lib.tree_query import TreeQuery

PART_LINE_RE = re.compile(r'^\s*\(Part\s+"[^"]*"\s+"([^"]+)"')


def _asc_parts(path: Path) -> list[str]:
    out: list[str] = []
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = PART_LINE_RE.match(ln)
        if m:
            out.append(m.group(1))
    return out


def _struct_parts(path: Path) -> list[tuple[int, str]]:
    t = decode_structural_components(path)
    tq = TreeQuery(t)
    comps = tq.find("Components")
    if comps is None:
        return []
    rows: list[tuple[int, str]] = []
    for n in comps.children("Part"):
        ref = str(n.scalar("RefDes", "")).strip()
        off = int(n.offset())
        if ref:
            rows.append((off, ref))
    rows.sort(key=lambda x: x[0])
    return rows


def _lcs_len(a: list[str], b: list[str]) -> int:
    # O(n*m), acceptable for sample sizes.
    n, m = len(a), len(b)
    dp = [0] * (m + 1)
    for i in range(1, n + 1):
        prev = 0
        for j in range(1, m + 1):
            cur = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev + 1
            else:
                dp[j] = max(dp[j], dp[j - 1])
            prev = cur
    return dp[m]


def analyze_pair(dch: Path, asc: Path) -> dict[str, Any]:
    asc_refs = _asc_parts(asc)
    struct_rows = _struct_parts(dch)
    struct_refs = [r for _o, r in struct_rows]

    lcs = _lcs_len(struct_refs, asc_refs)
    set_asc = set(asc_refs)
    set_struct = set(struct_refs)

    # Layer1 signature profile for structural Parts.
    data = read_bytes(dch)
    toks = tokenize_layer1(data)
    idx_by_start = {int(t.start): i for i, t in enumerate(toks)}
    sig_count: Counter[str] = Counter()
    for off, _ref in struct_rows:
        keys = _first_n_keys(toks, idx_by_start, off, n=8)
        sig = " | ".join(keys)
        if sig:
            sig_count[sig] += 1

    return {
        "dch": str(dch),
        "asc": str(asc),
        "asc_part_count": len(asc_refs),
        "struct_part_count": len(struct_refs),
        "exact_order_match": asc_refs == struct_refs,
        "lcs_len": lcs,
        "lcs_rate_vs_asc": float(lcs / len(asc_refs)) if asc_refs else 1.0,
        "lcs_rate_vs_struct": float(lcs / len(struct_refs)) if struct_refs else 1.0,
        "only_in_asc_count": len(set_asc - set_struct),
        "only_in_struct_count": len(set_struct - set_asc),
        "only_in_asc_sample": sorted(set_asc - set_struct)[:12],
        "only_in_struct_sample": sorted(set_struct - set_asc)[:12],
        "part_start_signature_top": [{"signature": k, "count": v} for k, v in sig_count.most_common(12)],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Compare ASC Part order with structural Part order and layer1 signatures.")
    ap.add_argument("--samples", required=True, help="Directory containing .dch/.asc pairs")
    ap.add_argument("--out", required=True, help="Output JSON file")
    args = ap.parse_args()

    sdir = Path(args.samples)
    dchs = sorted(sdir.glob("*.dch"))
    rows: list[dict[str, Any]] = []
    for dch in dchs:
        asc = sdir / f"{dch.stem}.asc"
        if not asc.exists():
            continue
        rows.append(analyze_pair(dch, asc))

    out = {
        "samples_dir": str(sdir),
        "pair_count": len(rows),
        "pairs": rows,
        "summary": {
            "exact_order_pairs": sum(1 for r in rows if bool(r["exact_order_match"])),
            "mean_lcs_rate_vs_asc": (sum(float(r["lcs_rate_vs_asc"]) for r in rows) / len(rows)) if rows else 1.0,
            "mean_lcs_rate_vs_struct": (sum(float(r["lcs_rate_vs_struct"]) for r in rows) / len(rows)) if rows else 1.0,
        },
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(
        f"wrote={out_path} pairs={len(rows)} "
        f"exact={out['summary']['exact_order_pairs']} "
        f"lcs_asc={out['summary']['mean_lcs_rate_vs_asc']:.4f}"
    )


if __name__ == "__main__":
    main()
