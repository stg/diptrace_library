"""File safety checks shared by commands that write derived output."""
from pathlib import Path


def require_distinct_paths(source, target):
    """Reject the same path, including existing symlink and hard-link aliases."""
    source, target = Path(source), Path(target)
    if source.resolve() == target.resolve() or (
        source.exists() and target.exists() and source.samefile(target)
    ):
        raise ValueError("input and output paths must differ")
