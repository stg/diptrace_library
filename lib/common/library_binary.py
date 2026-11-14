"""Shared scalar prefix for standalone library streams.

Adapters supply their own signature, version range, string transition and
field ordering. These transient values are consumed by the model constructor.
"""
from dataclasses import dataclass

from .errors import UnsupportedFileError


@dataclass(frozen=True)
class LibraryHeader:
    version: int
    entry_count: int | None
    name: str
    hint: str


def read_library_header(reader, *, signature, versions, unicode_since,
                        count_first, format, family):
    """Consume the prefix; a count after catalogue metadata belongs to the body."""
    size = reader.take(1)[0]
    if reader.take(size) != signature:
        raise reader.error_type(f'not a {family} library stream')
    version = reader.integer()
    if version not in versions:
        raise UnsupportedFileError(f'{format.upper()} version {version} is not supported',
            format=format, family=family, version=version, reason='version')
    reader.unicode_text = version >= unicode_since
    count = reader.count('library entries') if count_first else None
    name, hint = reader.text(), reader.text()
    return LibraryHeader(version, count, name, hint)
