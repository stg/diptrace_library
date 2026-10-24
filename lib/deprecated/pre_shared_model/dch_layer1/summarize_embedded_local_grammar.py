from __future__ import annotations

"""Summarize extracted embedded opcode grammar families across DCH files."""

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.deprecated.pre_shared_model.lib.opcode import decode_opcode_structure_tree


def _one(path_s: str) -> dict[str, object]:
    path = Path(path_s)
    family_counts: Counter[str] = Counter()
    family_code_counts: Counter[tuple[str, int | None]] = Counter()
    family_outer_counts: Counter[tuple[str, str]] = Counter()
    family_atom_counts: Counter[tuple[str, int]] = Counter()
    transitions: Counter[tuple[str, str]] = Counter()
    code_transitions: Counter[tuple[str, str]] = Counter()

    _tokens, _stream, tree = decode_opcode_structure_tree(path)
    for node in tree.iter_nodes():
        prev: str | None = None
        prev_code: int | None = None
        for emb in node.embedded_children:
            fam = str(emb.structure_type)
            code = emb.properties.get("LocalCode")
            family_counts[fam] += 1
            family_code_counts[(fam, code)] += 1
            family_outer_counts[(str(node.record.signature_hex), fam)] += 1
            family_atom_counts[(fam, int(emb.end_atom - emb.start_atom + 1))] += 1
            if prev is not None:
                transitions[(prev, fam)] += 1
                code_transitions[(f"{prev}|{prev_code}", f"{fam}|{code}")] += 1
            prev = fam
            prev_code = None if code is None else int(code)

    return {
        "path": str(path),
        "family_counts": dict(family_counts),
        "family_code_counts": {f"{fam}|{code}": count for (fam, code), count in family_code_counts.items()},
        "family_outer_counts": {f"{sig}|{fam}": count for (sig, fam), count in family_outer_counts.items()},
        "family_atom_counts": {f"{fam}|{atoms}": count for (fam, atoms), count in family_atom_counts.items()},
        "transitions": {f"{a}|{b}": count for (a, b), count in transitions.items()},
        "code_transitions": {f"{a}>{b}": count for (a, b), count in code_transitions.items()},
    }


def _iter_paths(inputs: list[str]) -> list[Path]:
    out: list[Path] = []
    for item in inputs:
        if any(ch in item for ch in "*?[]"):
            out.extend(sorted(Path().glob(item)))
        else:
            p = Path(item)
            if p.is_dir():
                out.extend(sorted(p.rglob("*.dch")))
            else:
                out.append(p)
    return out


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Summarize extracted embedded grammar families.")
    ap.add_argument("inputs", nargs="+", help="Input .dch files, globs, or directories")
    ap.add_argument("--workers", type=int, default=1, help="Worker processes for corpus mode")
    ap.add_argument("--progress-sec", type=float, default=10.0, help="Progress print interval in seconds")
    return ap


def main() -> int:
    args = build_parser().parse_args()
    paths = _iter_paths(args.inputs)
    if not paths:
        print("no input files found", file=sys.stderr)
        return 2

    family_counts: Counter[str] = Counter()
    family_code_counts: Counter[tuple[str, int | None]] = Counter()
    family_outer_counts: Counter[tuple[str, str]] = Counter()
    family_atom_counts: Counter[tuple[str, int]] = Counter()
    transitions: Counter[tuple[str, str]] = Counter()
    code_transitions: Counter[tuple[str, str]] = Counter()

    start = time.perf_counter()
    last_progress = start
    done = 0

    if int(args.workers) <= 1:
        for path in paths:
            got = _one(str(path))
            family_counts.update(got["family_counts"])
            for key, val in got["family_code_counts"].items():
                fam, code = key.rsplit("|", 1)
                family_code_counts[(fam, None if code == "None" else int(code))] += int(val)
            for key, val in got["family_outer_counts"].items():
                sig, fam = key.split("|", 1)
                family_outer_counts[(sig, fam)] += int(val)
            for key, val in got["family_atom_counts"].items():
                fam, atoms = key.rsplit("|", 1)
                family_atom_counts[(fam, int(atoms))] += int(val)
            for key, val in got["transitions"].items():
                a, b = key.split("|", 1)
                transitions[(a, b)] += int(val)
            for key, val in got["code_transitions"].items():
                a, b = key.split(">", 1)
                code_transitions[(a, b)] += int(val)
            done += 1
    else:
        with ProcessPoolExecutor(max_workers=int(args.workers)) as ex:
            futs = {ex.submit(_one, str(path)): path for path in paths}
            for fut in as_completed(futs):
                got = fut.result()
                family_counts.update(got["family_counts"])
                for key, val in got["family_code_counts"].items():
                    fam, code = key.rsplit("|", 1)
                    family_code_counts[(fam, None if code == "None" else int(code))] += int(val)
                for key, val in got["family_outer_counts"].items():
                    sig, fam = key.split("|", 1)
                    family_outer_counts[(sig, fam)] += int(val)
                for key, val in got["family_atom_counts"].items():
                    fam, atoms = key.rsplit("|", 1)
                    family_atom_counts[(fam, int(atoms))] += int(val)
                for key, val in got["transitions"].items():
                    a, b = key.split("|", 1)
                    transitions[(a, b)] += int(val)
                for key, val in got["code_transitions"].items():
                    a, b = key.split(">", 1)
                    code_transitions[(a, b)] += int(val)
                done += 1
                now = time.perf_counter()
                if now - last_progress >= float(args.progress_sec) or done == len(paths):
                    print(f"progress files={done}/{len(paths)} elapsed={now - start:.1f}s")
                    last_progress = now

    print("family_counts")
    for fam, count in family_counts.most_common():
        print(f"  {count:7d} {fam}")

    print("\nfamily_codes")
    for (fam, code), count in sorted(family_code_counts.items(), key=lambda kv: (-kv[1], kv[0][0], str(kv[0][1])))[:40]:
        print(f"  {count:7d} code={code!s:>4} {fam}")

    print("\nfamily_atom_counts")
    for (fam, atoms), count in sorted(family_atom_counts.items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][1]))[:40]:
        print(f"  {count:7d} atoms={atoms:>3} {fam}")

    print("\nfamily_transitions")
    for (a, b), count in transitions.most_common(40):
        print(f"  {count:7d} {a} -> {b}")

    print("\nfamily_code_transitions")
    for (a, b), count in code_transitions.most_common(40):
        print(f"  {count:7d} {a} -> {b}")

    print("\nfamily_outer_signatures")
    for (sig, fam), count in sorted(family_outer_counts.items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][1]))[:40]:
        print(f"  {count:7d} {sig} {fam}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
