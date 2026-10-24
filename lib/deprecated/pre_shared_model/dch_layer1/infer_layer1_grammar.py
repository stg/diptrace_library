from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.deprecated.pre_shared_model.lib.opcode.layer1 import OpcodeToken as L1Token, read_bytes, tokenize_opcode_layer as tokenize_layer1
from lib.deprecated.pre_shared_model.lib.structural.decoder import decode_structural_components, decode_structural_records


@dataclass(frozen=True)
class RecRef:
    start: int
    end: int
    length: int
    mode: int
    b2: int
    lead: int
    decoded_type: str
    refdes: str


def _token_key(t: L1Token) -> str:
    if t.kind == "OP0F" and t.value is not None:
        width = int(t.end - t.start)
        return f"{t.kind}:{int(t.value):0{width*2-2}x}"
    return t.kind


def _first_n_keys(tokens: list[L1Token], idx_by_start: dict[int, int], start: int, n: int = 8) -> list[str]:
    i = idx_by_start.get(int(start))
    if i is None:
        return []
    out: list[str] = []
    j = i
    lim = len(tokens)
    while j < lim and len(out) < n:
        out.append(_token_key(tokens[j]))
        j += 1
    return out


def _load_decoded_top_by_offset(tree: dict[str, Any]) -> dict[int, tuple[str, str]]:
    out: dict[int, tuple[str, str]] = {}

    def walk(node: dict[str, Any]) -> None:
        ni = node.get("_internal", {}) if isinstance(node.get("_internal"), dict) else {}
        if bool(ni.get("top_level", False)):
            off = ni.get("offset")
            t = str(node.get("type", ""))
            ref = ""
            props = node.get("props", {})
            if isinstance(props, dict):
                rv = props.get("RefDes", "")
                ref = str(rv) if isinstance(rv, str) else str(rv)
            if isinstance(off, int) and t:
                out[int(off)] = (t, ref)
        for ch in node.get("children", []) if isinstance(node.get("children"), list) else []:
            if isinstance(ch, dict):
                walk(ch)

    walk(tree)
    return out


def infer_for_file(path: Path) -> dict[str, Any]:
    data = read_bytes(path)
    toks = tokenize_layer1(data)
    idx_by_start = {int(t.start): i for i, t in enumerate(toks)}
    recs = decode_structural_records(data)
    tree = decode_structural_components(path)
    dec_by_off = _load_decoded_top_by_offset(tree)

    refs: list[RecRef] = []
    raw_start5: Counter[str] = Counter()
    raw_start8: Counter[str] = Counter()
    header_triplet: Counter[str] = Counter()
    for r in recs:
        d = dec_by_off.get(int(r.start), ("", ""))
        b2 = data[r.start + 2] if r.start + 2 < len(data) else -1
        raw_start5[data[r.start : r.start + 5].hex(" ")] += 1
        raw_start8[data[r.start : r.start + 8].hex(" ")] += 1
        header_triplet[f"b2={b2:02x},lead={int(r.lead):02x},mode={int(r.mode):02x}"] += 1
        refs.append(
            RecRef(
                start=int(r.start),
                end=int(r.end),
                length=int(r.length),
                mode=int(r.mode),
                b2=int(b2),
                lead=int(r.lead),
                decoded_type=str(d[0]),
                refdes=str(d[1]),
            )
        )

    # 1) Candidate start signatures.
    sig_counts: Counter[str] = Counter()
    sig_types: dict[str, Counter[str]] = defaultdict(Counter)
    id_token_counts: dict[int, Counter[str]] = defaultdict(Counter)
    for rr in refs:
        keys = _first_n_keys(toks, idx_by_start, rr.start, n=8)
        sig = " | ".join(keys)
        if sig == "":
            continue
        sig_counts[sig] += 1
        sig_types[sig][rr.decoded_type or ""] += 1
        for pos, k in enumerate(keys[:6]):
            id_token_counts[pos][k] += 1

    # 2) Candidate id fields from early token positions.
    id_by_type: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for rr in refs:
        keys = _first_n_keys(toks, idx_by_start, rr.start, n=6)
        if not keys:
            continue
        t = rr.decoded_type or "(unknown)"
        # use token slot 3 as primary id-candidate: stable in observed starts.
        if len(keys) > 3:
            id_by_type[t][keys[3]] += 1

    # 3) Length signal search among first tokens.
    # We only test direct equality/delta against record length.
    len_match: dict[int, Counter[int]] = defaultdict(Counter)  # pos -> delta -> count
    len_values: dict[int, Counter[int]] = defaultdict(Counter)  # pos -> value -> count
    for rr in refs:
        i = idx_by_start.get(rr.start)
        if i is None:
            continue
        for pos in range(0, 10):
            j = i + pos
            if j >= len(toks):
                break
            tv = toks[j].value
            if tv is None:
                continue
            v = int(tv)
            len_values[pos][v] += 1
            delta = rr.length - v
            if -4096 <= delta <= 4096:
                len_match[pos][delta] += 1

    
    trans: Counter[str] = Counter()
    trans_by_type: Counter[str] = Counter()
    for i in range(len(refs) - 1):
        a = refs[i]
        b = refs[i + 1]
        k = f"a(mode={a.mode:02x},b2={a.b2:02x},lead={a.lead:02x})->b(mode={b.mode:02x},b2={b.b2:02x},lead={b.lead:02x})"
        trans[k] += 1
        kt = f"{a.decoded_type or '?'} -> {b.decoded_type or '?'} | {k}"
        trans_by_type[kt] += 1

    # 5) Largest spans as anomaly candidates.
    big = sorted(refs, key=lambda x: x.length, reverse=True)[:20]

    return {
        "file": str(path),
        "size": len(data),
        "token_count": len(toks),
        "record_count": len(refs),
        "start_signature_top": [
            {
                "signature": k,
                "count": v,
                "types_top": [{"type": tk, "count": tv} for tk, tv in sig_types[k].most_common(6)],
            }
            for k, v in sig_counts.most_common(20)
        ],
        "raw_start5_top": [{"start5": k, "count": v} for k, v in raw_start5.most_common(20)],
        "raw_start8_top": [{"start8": k, "count": v} for k, v in raw_start8.most_common(20)],
        "header_triplet_top": [{"triplet": k, "count": v} for k, v in header_triplet.most_common(20)],
        "id_token_position_top": {
            str(pos): [{"token": tk, "count": tv} for tk, tv in c.most_common(12)]
            for pos, c in sorted(id_token_counts.items(), key=lambda kv: kv[0])
        },
        "id_candidate_by_type_slot3": {
            t: [{"token": tk, "count": tv} for tk, tv in Counter(m).most_common(8)]
            for t, m in sorted(id_by_type.items())
        },
        "length_delta_top_by_pos": {
            str(pos): [{"delta": d, "count": c} for d, c in cnt.most_common(10)]
            for pos, cnt in sorted(len_match.items(), key=lambda kv: kv[0])
        },
        "length_value_top_by_pos": {
            str(pos): [{"value": d, "count": c} for d, c in cnt.most_common(10)]
            for pos, cnt in sorted(len_values.items(), key=lambda kv: kv[0])
        },
        "adjacent_transition_top": [{"transition": k, "count": v} for k, v in trans.most_common(24)],
        "adjacent_transition_with_types_top": [{"transition": k, "count": v} for k, v in trans_by_type.most_common(24)],
        "longest_records": [
            {
                "start": r.start,
                "end": r.end,
                "len": r.length,
                "decoded_type": r.decoded_type,
                "refdes": r.refdes,
                "lead": r.lead,
                "mode": r.mode,
                "b2": r.b2,
                "start_tokens": _first_n_keys(toks, idx_by_start, r.start, n=8),
            }
            for r in big
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Infer first-layer grammar candidates (start markers, ids, lengths, depth transitions)."
    )
    ap.add_argument("--samples", required=True, help="Directory with .dch files")
    ap.add_argument("--out", required=True, help="Output JSON file")
    args = ap.parse_args()

    sample_dir = Path(args.samples)
    files = sorted(sample_dir.glob("*.dch"))
    reports = [infer_for_file(fp) for fp in files]

    # Small global merge.
    gsig: Counter[str] = Counter()
    gtrans: Counter[str] = Counter()
    gstart5: Counter[str] = Counter()
    gtrip: Counter[str] = Counter()
    for r in reports:
        for s in r["start_signature_top"]:
            gsig[str(s["signature"])] += int(s["count"])
        for t in r["adjacent_transition_top"]:
            gtrans[str(t["transition"])] += int(t["count"])
        for s in r["raw_start5_top"]:
            gstart5[str(s["start5"])] += int(s["count"])
        for t in r["header_triplet_top"]:
            gtrip[str(t["triplet"])] += int(t["count"])

    payload = {
        "samples_dir": str(sample_dir),
        "file_count": len(reports),
        "files": reports,
        "global": {
            "start_signature_top": [{"signature": k, "count": v} for k, v in gsig.most_common(30)],
            "raw_start5_top": [{"start5": k, "count": v} for k, v in gstart5.most_common(20)],
            "header_triplet_top": [{"triplet": k, "count": v} for k, v in gtrip.most_common(20)],
            "adjacent_transition_top": [{"transition": k, "count": v} for k, v in gtrans.most_common(30)],
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    total_recs = sum(int(r["record_count"]) for r in reports)
    print(f"wrote={out} files={len(reports)} records={total_recs}")


if __name__ == "__main__":
    main()
