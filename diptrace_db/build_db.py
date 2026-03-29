from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.lib.dch_model import (
    detect_pattern_records_from_binary,
    extract_len16_utf16_noterm_stream,
    extract_len16_utf16_stream,
    infer_component_records_from_stream,
    read_bytes,
)


SKIP_DIRS = {".git", "node_modules", "__pycache__", ".vs", ".idea"}


def _extract_file_rows(dch_path: Path) -> list[tuple[str, str, str]]:
    data = read_bytes(dch_path)
    lstr = extract_len16_utf16_stream(data, min_len=1, max_len=256)
    lshort = extract_len16_utf16_noterm_stream(data, min_len=1, max_len=256)
    comps = infer_component_records_from_stream(lstr, lshort, data=data)
    comps = detect_pattern_records_from_binary(data, comps)

    out: list[tuple[str, str, str]] = []
    for c in comps:
        name = str(c.get("part_name", "")).strip(" \t")
        value = str(c.get("value", "")).strip(" \t")
        pattern = str(c.get("pattern", {}).get("name", "")).strip(" \t") if isinstance(c.get("pattern"), dict) else ""
        # Normalize generic names duplicated as prefix in pattern names, e.g. RES + RES_0603.
        if name and pattern.startswith(name):
            tail = pattern[len(name) :]
            if tail == "" or (tail and not tail[0].isalnum()):
                name = ""
        out.append((name, value, pattern))
    return out


def _worker(dch_str: str) -> dict[str, Any]:
    dch = Path(dch_str)
    st = dch.stat()
    rows = _extract_file_rows(dch)
    unique_rows = sorted(set(rows))
    missing_value = sum(1 for _, value, _ in rows if value == "")
    missing_pattern = sum(1 for _, _, pat in rows if pat == "")
    return {
        "file": str(dch),
        "rows": unique_rows,
        "component_count": len(rows),
        "unique_combo_count": len(unique_rows),
        "missing_value_count": missing_value,
        "missing_pattern_count": missing_pattern,
        "file_size_bytes": int(st.st_size),
        "mtime_ns": int(st.st_mtime_ns),
    }


def _load_previous_index(out_path: Path) -> dict[str, dict[str, Any]]:
    if not out_path.exists():
        return {}
    try:
        prev = json.loads(out_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}

    prev_files = prev.get("files", [])
    prev_stats = prev.get("file_stats", [])
    prev_unique = prev.get("file_unique", [])

    stats_by_file: dict[str, dict[str, Any]] = {}
    for r in prev_stats:
        f = str(r.get("file", ""))
        if f:
            stats_by_file[f] = r

    unique_by_file: dict[str, list[tuple[str, str, str]]] = {}
    for r in prev_unique:
        f = str(r.get("file", ""))
        rows = r.get("unique", [])
        if not f or not isinstance(rows, list):
            continue
        parsed: list[tuple[str, str, str]] = []
        for x in rows:
            if isinstance(x, list) and len(x) == 3:
                parsed.append((str(x[0]), str(x[1]), str(x[2])))
            elif isinstance(x, dict):
                parsed.append((str(x.get("name", "")), str(x.get("value", "")), str(x.get("pattern", ""))))
        unique_by_file[f] = parsed

    out: dict[str, dict[str, Any]] = {}
    for r in prev_files:
        f = str(r.get("file", ""))
        if not f:
            continue
        try:
            mtime_ns = int(r.get("mtime_ns", -1))
            size_bytes = int(r.get("size_bytes", -1))
        except (TypeError, ValueError):
            continue
        out[f] = {
            "mtime_ns": mtime_ns,
            "size_bytes": size_bytes,
            "stats": stats_by_file.get(f),
            "unique_rows": unique_by_file.get(f),
        }
    return out


def _print_progress(
    *,
    dirs_scanned: int,
    dirs_found: int,
    discovered_dch: int,
    unique_done: int,
    unique_total_estimate: int,
    extracted: int,
    reused: int,
    components_processed: int,
    components_extracted: int,
    failures: int,
    started: float,
) -> None:
    elapsed = time.time() - started
    rate = int(round(components_extracted / elapsed)) if elapsed > 0 else 0
    files_processed = reused + extracted
    print(
        f"dirs={dirs_scanned}/{dirs_found} files={files_processed}/{discovered_dch} "
        f"failed={failures} unique={unique_done}/{max(unique_done, unique_total_estimate)} "
        f"rate={rate}/s"
    )


def build_db(root: Path, workers: int, prev_index: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    if prev_index is None:
        prev_index = {}
    failures: list[dict[str, str]] = []

    started = time.time()
    last_progress = 0.0
    discovered_dch = 0
    dirs_scanned = 0
    dirs_found = 1
    extracted = 0
    reused = 0
    components_processed = 0
    components_extracted = 0
    root = root.resolve()
    per_file_stats_map: dict[str, dict[str, Any]] = {}
    per_file_rows_map: dict[str, list[tuple[str, str, str]]] = {}
    file_manifest_map: dict[str, dict[str, Any]] = {}
    unique_done: set[tuple[str, str, str]] = set()
    unique_total_estimate: set[tuple[str, str, str]] = set()

    def maybe_print_progress(force: bool = False) -> None:
        nonlocal last_progress
        now = time.time()
        if force or (now - last_progress >= 1.0):
            _print_progress(
                dirs_scanned=dirs_scanned,
                dirs_found=dirs_found,
                discovered_dch=discovered_dch,
                unique_done=len(unique_done),
                unique_total_estimate=len(unique_total_estimate),
                extracted=extracted,
                reused=reused,
                components_processed=components_processed,
                components_extracted=components_extracted,
                failures=len(failures),
                started=started,
            )
            last_progress = now

    # Streaming traversal + processing:
    # target_discovered increases as new folders are scanned.
    stack: list[Path] = [root]
    max_pending = max(16, workers * 8)
    fut_to_path: dict[Any, Path] = {}
    pending: set[Any] = set()
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
                                    fp = str(Path(ent.path))
                                    try:
                                        st = ent.stat(follow_symlinks=False)
                                    except OSError as e:
                                        failures.append({"file": fp, "error": repr(e)})
                                        continue
                                    cur_mtime_ns = int(st.st_mtime_ns)
                                    cur_size = int(st.st_size)
                                    file_manifest_map[fp] = {"file": fp, "mtime_ns": cur_mtime_ns, "size_bytes": cur_size}

                                    prev = prev_index.get(fp)
                                    can_reuse = (
                                        prev is not None
                                        and int(prev.get("mtime_ns", -1)) == cur_mtime_ns
                                        and int(prev.get("size_bytes", -1)) == cur_size
                                        and isinstance(prev.get("stats"), dict)
                                        and isinstance(prev.get("unique_rows"), list)
                                    )
                                    if can_reuse:
                                        reused += 1
                                        s = dict(prev["stats"])
                                        s["file"] = fp
                                        per_file_stats_map[fp] = {
                                            "file": fp,
                                            "component_count": int(s.get("component_count", 0)),
                                            "unique_combo_count": int(s.get("unique_combo_count", 0)),
                                            "missing_value_count": int(s.get("missing_value_count", 0)),
                                            "missing_pattern_count": int(s.get("missing_pattern_count", 0)),
                                        }
                                        components_processed += int(s.get("component_count", 0))
                                        per_file_rows_map[fp] = [(str(a), str(b), str(c)) for a, b, c in prev["unique_rows"]]
                                        for t in per_file_rows_map[fp]:
                                            unique_done.add(t)
                                            unique_total_estimate.add(t)
                                    else:
                                        if prev is not None and isinstance(prev.get("unique_rows"), list):
                                            for a, b, c in prev["unique_rows"]:
                                                unique_total_estimate.add((str(a), str(b), str(c)))
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

            done, still = wait(pending, timeout=0.25, return_when=FIRST_COMPLETED)
            pending = set(still)
            for fut in done:
                src = fut_to_path.pop(fut)
                try:
                    row = fut.result()
                except Exception as e:  # noqa: BLE001
                    failures.append({"file": str(src), "error": repr(e)})
                    extracted += 1
                    continue

                fp = str(row["file"])
                per_file_stats_map[fp] = {
                    "file": fp,
                    "component_count": int(row["component_count"]),
                    "unique_combo_count": int(row["unique_combo_count"]),
                    "missing_value_count": int(row["missing_value_count"]),
                    "missing_pattern_count": int(row["missing_pattern_count"]),
                }
                per_file_rows_map[fp] = [(str(a), str(b), str(c)) for a, b, c in row["rows"]]
                for t in per_file_rows_map[fp]:
                    unique_done.add(t)
                    unique_total_estimate.add(t)
                file_manifest_map[fp] = {
                    "file": fp,
                    "mtime_ns": int(row["mtime_ns"]),
                    "size_bytes": int(row["file_size_bytes"]),
                }
                components_processed += int(row["component_count"])
                components_extracted += int(row["component_count"])
                extracted += 1

            maybe_print_progress()

    # Final progress snapshot at completion, before aggregation/output.
    maybe_print_progress(force=True)

    combo_to_files: dict[tuple[str, str, str], set[str]] = {}
    for fp, rows in per_file_rows_map.items():
        for combo in rows:
            combo_to_files.setdefault(combo, set()).add(fp)

    combos = []
    for (name, value, pattern), files in sorted(combo_to_files.items()):
        flist = sorted(files)
        combos.append(
            {
                "name": name,
                "value": value,
                "pattern": pattern,
                "files": flist,
            }
        )

    per_file = sorted(per_file_stats_map.values(), key=lambda x: x["file"])
    scanned_files = [file_manifest_map[k] for k in sorted(file_manifest_map.keys())]
    total_components_processed = sum(int(r.get("component_count", 0)) for r in per_file)
    file_unique = [
        {"file": fp, "unique": [list(t) for t in per_file_rows_map.get(fp, [])]}
        for fp in sorted(per_file_rows_map.keys())
    ]
    result = {
        "root": str(root),
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "files_read": extracted,
        "files_failed": len(failures),
        "total_components_processed": int(total_components_processed),
        "unique_components": len(combos),
        "unique": combos,
        "file_stats": per_file,
        "failures": sorted(failures, key=lambda r: r["file"]),
        "files": scanned_files,
        "file_unique": file_unique,
    }
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Build central database of (name,value,pattern) -> files from all .dch files.")
    ap.add_argument("--root", default=r"D:\Sync\ExternalProjects", help="Root directory to scan recursively for .dch files.")
    ap.add_argument("--out", default="analysis/component_combo_db.json", help="Output JSON file.")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 1), help="Worker process count.")
    ap.add_argument("--clean", action="store_true", help="Ignore existing output DB cache and do a full rebuild.")
    args = ap.parse_args()

    root = Path(args.root)
    out = Path(args.out)
    if not root.exists():
        raise SystemExit(f"root not found: {root}")

    print(f"scan_root={root}")
    print(f"workers={args.workers}")
    prev_index: dict[str, dict[str, Any]] = {}
    if not args.clean:
        prev_index = _load_previous_index(out)
        if prev_index:
            print(f"cache_index_files={len(prev_index)}")
    else:
        print("cache=disabled (--clean)")
    db = build_db(root, workers=max(1, args.workers), prev_index=prev_index)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(db, indent=2), encoding="utf-8")
    print(
        f"wrote={out} files_read={db['files_read']} files_failed={db['files_failed']} "
        f"unique_components={db['unique_components']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
