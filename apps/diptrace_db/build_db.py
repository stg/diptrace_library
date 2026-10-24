"""Find which schematics use each component, reusing unchanged designs."""
import argparse
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import dataclass, field
import json
import os
from pathlib import Path

from lib import ConversionReport, read
from apps.common.components import physical_components
from apps.common.cli import Console, PROCESSING_ERRORS, add_report_argument
from .database import (
    FileComponents, FileStamp, assemble_database, cached_files, read_database,
)
from .paths import default_database_path

SKIP_DIRECTORIES = {".git", "node_modules", "__pycache__", ".vs", ".idea"}


@dataclass
class BuildResult:
    """Run diagnostics stay in memory, outside the saved usage database."""
    files: list[FileComponents] = field(default_factory=list)
    failures: list[tuple[Path, str]] = field(default_factory=list)
    read_count: int = 0
    reused_count: int = 0


def schematic_paths(root: Path, failures: list[tuple[Path, str]]):
    """Walk once without following directory links or entering tool metadata."""
    directories = [root]
    while directories:
        directory = directories.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name.lower() not in SKIP_DIRECTORIES:
                            directories.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        if Path(entry.name).suffix.lower() == ".dch":
                            yield Path(entry.path)
        except OSError as error:
            failures.append((directory, str(error)))


def read_components(path: Path) -> FileComponents:
    """Extract identity without changing authored names, values or patterns."""
    stamp = FileStamp.read(path)
    report = ConversionReport()
    design = read(path, report=report)
    components = {component.signature for component in physical_components(design)}
    if FileStamp.read(path) != stamp:
        raise OSError("design changed during the scan; run again to index it")
    return FileComponents(path, stamp, components, tuple(report.notices))


def build_db(root: Path, workers: int = 1, previous: dict | None = None) -> BuildResult:
    """Scan a supplied root; failed designs are reported and retried next time."""
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"scan root is not a directory: {root}")
    if workers < 1:
        raise ValueError("worker count must be positive")
    cache = cached_files(previous, root)
    result = BuildResult()

    def changed_paths():
        for path in schematic_paths(root, result.failures):
            try:
                stamp = FileStamp.read(path)
            except OSError as error:
                result.failures.append((path, str(error)))
                continue
            cached = cache.get(path)
            # Metadata is cheap to check. Only new or modified designs require
            # import; deleted files naturally disappear from the next output.
            if cached is not None and cached.stamp == stamp:
                result.files.append(cached)
                result.reused_count += 1
            else:
                yield path

    def collect(path, load):
        try:
            result.files.append(load())
            result.read_count += 1
        except Exception as error:
            # Isolate a bad file without hiding it. The CLI reports the failure,
            # and its absence from the cache ensures a retry on the next run.
            result.failures.append((path, str(error)))

    if workers == 1:
        # Avoid process startup and additional model copies for ordinary scans.
        for path in changed_paths():
            collect(path, lambda: read_components(path))
        return result

    paths = iter(changed_paths())
    with ProcessPoolExecutor(max_workers=workers) as executor:
        pending = {}
        while True:
            # Bound queued work even when a directory contains many designs.
            # Completion, rather than a timer, drives the next submission.
            while len(pending) < workers * 2:
                try:
                    path = next(paths)
                except StopIteration:
                    break
                pending[executor.submit(read_components, path)] = path
            if not pending:
                break
            completed, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in completed:
                collect(pending.pop(future), future.result)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="diptrace_db", description=__doc__)
    parser.add_argument("--root", type=Path, help="scan directory; required for a new database")
    parser.add_argument("--out", type=Path, help="database path; default: Documents/DipTraceLibrary/component_db.json")
    parser.add_argument("--workers", type=int, default=1, help="parallel readers (default: 1)")
    parser.add_argument("--clean", action="store_true", help="reread every file, keeping the saved root")
    add_report_argument(parser)
    args = parser.parse_args(argv)
    console = Console(args.report_level)
    if args.workers < 1:
        parser.error("--workers must be positive")

    try:
        output = args.out if args.out is not None else default_database_path()
    except OSError as error:
        return console.failure("cannot resolve the default database location; supply --out instead", error)
    if args.out is None:
        console.info(f"Using default output at {output}")
    previous = read_database(output)
    root = args.root
    if root is None and previous and isinstance(previous.get("root"), str):
        if previous["root"].strip():
            root = Path(previous["root"])
    if root is None:
        parser.error(f"no scan directory is saved in {output}; supply --root DIRECTORY")
    root = root.resolve()
    if not root.exists():
        parser.error(f"directory {root} does not exist; check it or supply another with --root")
    if not root.is_dir():
        parser.error(f"{root} is not a directory; supply another with --root")

    try:
        console.info(f"Scanning {root}")
        result = build_db(root, args.workers, None if args.clean else previous)
        database = assemble_database(root, result.files)
        # Complete scanning and serialization before opening the destination.
        data = json.dumps(database, indent=2, ensure_ascii=False) + "\n"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(data, encoding="utf-8")
    except PROCESSING_ERRORS as error:
        return console.failure("database build failed", error)

    for entry in sorted(result.files, key=lambda entry: entry.path):
        console.report(ConversionReport(list(entry.notices)))
    for path, message in sorted(result.failures):
        console.diagnostic("error", f"Skipped {path}: {message}")
    console.info(f"Wrote {output}: {len(database['components'])} components, "
                 f"{result.read_count} files read, {result.reused_count} reused, "
                 f"{len(result.failures)} skipped")
    return 1 if result.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
