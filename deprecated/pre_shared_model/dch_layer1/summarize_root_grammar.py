from __future__ import annotations

"""Summarize depth-0 outer-record grammar across DCH files."""

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.deprecated.pre_shared_model.lib.opcode import decode_opcode_structure_tree


def _one(path_s: str) -> dict[str, object]:
    path = Path(path_s)
    root_counts: Counter[str] = Counter()
    root_transitions: Counter[tuple[str, str]] = Counter()
    root_runs: Counter[tuple[str, int]] = Counter()
    root_childsets: Counter[tuple[str, ...]] = Counter()

    _tokens, _stream, tree = decode_opcode_structure_tree(path)
    roots = list(tree.roots)
    sigs = [str(node.record.signature_hex) for node in roots]
    for sig in sigs:
        root_counts[sig] += 1
    for a, b in zip(sigs, sigs[1:]):
        root_transitions[(a, b)] += 1
    i = 0
    while i < len(sigs):
        j = i + 1
        while j < len(sigs) and sigs[j] == sigs[i]:
            j += 1
        root_runs[(sigs[i], int(j - i))] += 1
        i = j
    for node in roots:
        root_childsets[tuple(str(ch.record.signature_hex) for ch in node.children)] += 1

    return {
        "root_counts": dict(root_counts),
        "root_transitions": {f"{a}|{b}": count for (a, b), count in root_transitions.items()},
        "root_runs": {f"{sig}|{run_len}": count for (sig, run_len), count in root_runs.items()},
        "root_childsets": {"|".join(childset): count for childset, count in root_childsets.items()},
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
    ap = argparse.ArgumentParser(description="Summarize root-level outer-record grammar.")
    ap.add_argument("inputs", nargs="+", help="Input .dch files, directories, or globs")
    ap.add_argument("--workers", type=int, default=1, help="Worker processes")
    ap.add_argument("--progress-sec", type=float, default=10.0, help="Progress print interval")
    return ap


def main() -> int:
    args = build_parser().parse_args()
    paths = _iter_paths(args.inputs)
    if not paths:
        print("no input files found", file=sys.stderr)
        return 2

    root_counts: Counter[str] = Counter()
    root_transitions: Counter[tuple[str, str]] = Counter()
    root_runs: Counter[tuple[str, int]] = Counter()
    root_childsets: Counter[tuple[str, ...]] = Counter()

    start = time.perf_counter()
    last_progress = start
    done = 0

    def _merge(got: dict[str, object]) -> None:
        root_counts.update(got["root_counts"])
        for key, val in got["root_transitions"].items():
            a, b = key.split("|", 1)
            root_transitions[(a, b)] += int(val)
        for key, val in got["root_runs"].items():
            sig, run_len = key.rsplit("|", 1)
            root_runs[(sig, int(run_len))] += int(val)
        for key, val in got["root_childsets"].items():
            childset = tuple(part for part in key.split("|") if part)
            root_childsets[childset] += int(val)

    if int(args.workers) <= 1:
        for path in paths:
            _merge(_one(str(path)))
            done += 1
    else:
        with ProcessPoolExecutor(max_workers=int(args.workers)) as ex:
            futs = {ex.submit(_one, str(path)): path for path in paths}
            for fut in as_completed(futs):
                _merge(fut.result())
                done += 1
                now = time.perf_counter()
                if now - last_progress >= float(args.progress_sec) or done == len(paths):
                    print(f"progress files={done}/{len(paths)} elapsed={now - start:.1f}s")
                    last_progress = now

    print("root_counts")
    for sig, count in root_counts.most_common(40):
        print(f"  {count:7d} {sig}")

    print("\nroot_transitions")
    for (a, b), count in root_transitions.most_common(40):
        print(f"  {count:7d} {a} -> {b}")

    print("\nroot_runs")
    for (sig, run_len), count in sorted(root_runs.items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][1]))[:60]:
        print(f"  {count:7d} run={run_len:>3} {sig}")

    print("\nroot_childsets")
    for childset, count in root_childsets.most_common(40):
        rendered = " | ".join(childset) if childset else "(none)"
        print(f"  {count:7d} {rendered}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
