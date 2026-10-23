from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.deprecated.pre_shared_model.lib.opcode.layer1 import parse_layer1_events, verify_full_coverage


SKIP_DIRS = {".git", "node_modules", "__pycache__", ".vs", ".idea"}


def _worker(dch_str: str) -> dict[str, Any]:
    path = Path(dch_str)
    st = path.stat()
    data = path.read_bytes()
    events = parse_layer1_events(data)
    ok, message = verify_full_coverage(data, events)
    if not ok:
        raise RuntimeError(message)
    kind_counts: dict[str, int] = {}
    for ev in events:
        kind_counts[ev.kind] = int(kind_counts.get(ev.kind, 0) + 1)
    return {
        "file": str(path),
        "size_bytes": int(st.st_size),
        "mtime_ns": int(st.st_mtime_ns),
        "token_count": int(len(events)),
        "kind_counts": kind_counts,
    }


def _print_progress(
    *,
    dirs_scanned: int,
    dirs_found: int,
    files_done: int,
    discovered_dch: int,
    files_failed: int,
    tokens_done: int,
    started: float,
) -> None:
    elapsed = time.time() - started
    rate = int(round(files_done / elapsed)) if elapsed > 0 else 0
    print(
        f"dirs={dirs_scanned}/{dirs_found} files={files_done}/{discovered_dch} "
        f"failed={files_failed} tokens={tokens_done} rate={rate}/s"
    )


def stress_lexer(root: Path, workers: int) -> dict[str, Any]:
    root = root.resolve()
    started = time.time()
    last_progress = 0.0
    dirs_scanned = 0
    dirs_found = 1
    discovered_dch = 0
    files_done = 0
    tokens_done = 0
    failures: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    aggregate_kinds: dict[str, int] = {}

    def maybe_print_progress(force: bool = False) -> None:
        nonlocal last_progress
        now = time.time()
        if force or (now - last_progress >= 1.0):
            _print_progress(
                dirs_scanned=dirs_scanned,
                dirs_found=dirs_found,
                files_done=files_done,
                discovered_dch=discovered_dch,
                files_failed=len(failures),
                tokens_done=tokens_done,
                started=started,
            )
            last_progress = now

    stack: list[Path] = [root]
    pending: set[Any] = set()
    fut_to_path: dict[Any, Path] = {}
    max_pending = max(16, workers * 8)

    with ProcessPoolExecutor(max_workers=workers) as ex:
        while stack or pending:
            while stack and len(pending) < max_pending:
                cur = stack.pop()
                dirs_scanned += 1
                try:
                    with os.scandir(cur) as it:
                        for ent in it:
                            try:
                                if ent.is_dir(follow_symlinks=False):
                                    if ent.name.lower() in SKIP_DIRS:
                                        continue
                                    stack.append(Path(ent.path))
                                    dirs_found += 1
                                elif ent.is_file(follow_symlinks=False) and ent.name.lower().endswith(".dch"):
                                    discovered_dch += 1
                                    fut = ex.submit(_worker, ent.path)
                                    pending.add(fut)
                                    fut_to_path[fut] = Path(ent.path)
                            except OSError:
                                continue
                except OSError as e:
                    failures.append({"file": str(cur), "error": repr(e)})
                maybe_print_progress()

            if not pending:
                continue

            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for fut in done:
                path = fut_to_path.pop(fut)
                try:
                    res = fut.result()
                    results.append(res)
                    files_done += 1
                    tokens_done += int(res.get("token_count", 0))
                    for kind, count in res.get("kind_counts", {}).items():
                        aggregate_kinds[kind] = int(aggregate_kinds.get(kind, 0) + int(count))
                except Exception as e:  # noqa: BLE001
                    files_done += 1
                    failures.append({"file": str(path), "error": repr(e)})
                maybe_print_progress()

    maybe_print_progress(force=True)
    elapsed = time.time() - started
    return {
        "root": str(root),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
        "workers": int(workers),
        "files_total": int(discovered_dch),
        "files_ok": int(len(results)),
        "files_failed": int(len(failures)),
        "dirs_scanned": int(dirs_scanned),
        "dirs_found": int(dirs_found),
        "token_count": int(tokens_done),
        "duration_sec": int(round(elapsed)),
        "kind_counts": dict(sorted(aggregate_kinds.items())),
        "failures": failures,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Lexer-only corpus stress test for DipTrace DCH layer1.")
    ap.add_argument("--root", required=True, help="Root directory to scan recursively for .dch files.")
    ap.add_argument("--out", required=True, help="Output JSON report.")
    ap.add_argument(
        "--workers", type=int, default=max(1, (os.cpu_count() or 4) - 1), help="Worker process count."
    )
    args = ap.parse_args()

    root = Path(args.root)
    out_path = Path(args.out)
    print(f"root={root}")
    print(f"workers={args.workers}")
    report = stress_lexer(root, workers=max(1, args.workers))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"wrote={out_path} files_total={report['files_total']} "
        f"files_ok={report['files_ok']} files_failed={report['files_failed']}"
    )


if __name__ == "__main__":
    main()
