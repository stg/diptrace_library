"""Atomic output and inexpensive, worktree-local change detection."""
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=True, indent=2) + '\n').encode('utf-8')


def read_json(path):
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, UnicodeError) as error:
        raise ValueError(f'invalid JSON in {path}: {error}') from None
    if not isinstance(value, dict):
        raise ValueError(f'{path}: expected a JSON object')
    return value


def digest(data, *, text=False):
    # Git may check text out with different line endings. That alone must not
    # replace an otherwise untouched original binary.
    if text:
        data = data.replace(b'\r\n', b'\n')
    return hashlib.sha256(data).hexdigest()


def atomic_write(path, data):
    """Replace a complete file, leaving identical output and its mtime alone."""
    if path.is_file() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.diptrace-git-', delete=False) as out:
            name = Path(out.name)
            out.write(data)
        os.replace(name, path)
    finally:
        if name is not None and name.exists():
            name.unlink()
    return True


@dataclass(frozen=True)
class Stamp:
    mtime_ns: int
    ctime_ns: int
    size: int

    @classmethod
    def read(cls, path):
        stat = path.stat()
        return cls(stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size)


@dataclass
class Snapshot:
    stamp: Stamp
    sha256: str
    data: bytes | None = None

    def saved(self):
        return {'stamp': asdict(self.stamp), 'sha256': self.sha256}


def snapshot(path, cached=None, *, text=False, verify=False):
    if not path.exists():
        return None
    stamp = Stamp.read(path)
    if not verify and cached and cached.get('stamp') == asdict(stamp):
        return Snapshot(stamp, cached['sha256'])
    data = path.read_bytes()
    if Stamp.read(path) != stamp:
        raise ValueError(f'{path}: changed while being read; save and try again')
    return Snapshot(stamp, digest(data, text=text), data)


def unchanged(path, before):
    """Recheck immediately before replacing output, including absent outputs."""
    if before is None:
        return not path.exists()
    return path.exists() and Stamp.read(path) == before.stamp
