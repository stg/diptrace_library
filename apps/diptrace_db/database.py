"""The usage database and its incremental-read cache.

Component-to-file links are the data. File timestamps and sizes let the next
scan reuse those same links, without storing a second component index.
"""
from dataclasses import asdict, dataclass
import json
from pathlib import Path

from apps.common.components import Signature
from lib import ConversionNotice

DATABASE_VERSION = 2


@dataclass(frozen=True)
class FileStamp:
    mtime_ns: int
    size_bytes: int

    @classmethod
    def read(cls, path: Path) -> "FileStamp":
        stat = path.stat()
        return cls(stat.st_mtime_ns, stat.st_size)


@dataclass
class FileComponents:
    path: Path
    stamp: FileStamp
    components: set[Signature]
    # Import diagnostics are presented by the CLI, never serialized as usage.
    notices: tuple[ConversionNotice, ...] = ()


def read_database(path: Path) -> dict | None:
    """Return the saved document, or None when it is absent or unreadable."""
    try:
        database = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return database if isinstance(database, dict) else None


def cached_files(database: dict | None, root: Path) -> dict[Path, FileComponents]:
    """Recover per-file facts from the saved links; never reuse another root."""
    if not database or database.get("version") != DATABASE_VERSION:
        return {}
    if database.get("root") != str(root):
        return {}
    stamps = database.get("files")
    components = database.get("components")
    if not isinstance(stamps, dict) or not isinstance(components, list):
        return {}

    files = {}
    try:
        for relative, stamp in stamps.items():
            if not isinstance(relative, str):
                return {}
            mtime, size = stamp["mtime_ns"], stamp["size_bytes"]
            if type(mtime) is not int or type(size) is not int or size < 0:
                return {}
            files[relative] = FileComponents(root / relative, FileStamp(mtime, size), set())
        for component in components:
            signature = component["name"], component["value"], component["pattern"]
            if not all(isinstance(value, str) for value in signature):
                return {}
            if not isinstance(component["files"], list):
                return {}
            for relative in component["files"]:
                files[relative].components.add(signature)
    except (KeyError, TypeError):
        # An incomplete cache must not silently remove component usage. Parsing
        # the designs again is preferable to trusting malformed cached links.
        return {}
    return {entry.path: entry for entry in files.values()}


def assemble_database(root: Path, files: list[FileComponents]) -> dict:
    """Produce deterministic output with one owner for every saved fact."""
    stamps = {}
    usage: dict[Signature, list[str]] = {}
    for entry in sorted(files, key=lambda entry: entry.path):
        relative = entry.path.relative_to(root).as_posix()
        stamps[relative] = asdict(entry.stamp)
        for signature in sorted(entry.components):
            usage.setdefault(signature, []).append(relative)

    return {
        "version": DATABASE_VERSION,
        "root": str(root),
        "files": stamps,
        "components": [
            {"name": name, "value": value, "pattern": pattern, "files": paths}
            for (name, value, pattern), paths in sorted(usage.items())
        ],
    }
