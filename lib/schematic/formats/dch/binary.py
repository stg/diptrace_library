"""DCH byte cursor and version policy, independent of the document model."""
from __future__ import annotations

from dataclasses import dataclass
from ....common.binary import BinaryReader
from ....common.errors import UnsupportedFileError
from ..capabilities import DCH


MIN_VERSION = min(DCH.read_versions)
MAX_KNOWN_VERSION = max(DCH.read_versions)
_LEGACY_HEADERS = {"DTSCHEM2.22": 29, "DTSCHEM2.21": 28, "DTSCHEM2.2": 27}


class DchError(ValueError):
    pass


class UnsupportedVersionError(DchError, UnsupportedFileError):
    """DCH compatibility name for the shared unsupported-file error."""

    def __init__(self, message, *, version=None, reason='version'):
        super().__init__(message, format='dch', family='schematic', version=version, reason=reason)


@dataclass(frozen=True)
class Header:
    signature: str
    version: int
    body_offset: int

    @property
    def unicode_text(self):
        return self.version >= 32

    @property
    def angles_in_degrees(self):
        return self.version < 40


def read_header(data: bytes) -> Header:
    if not data or len(data) < data[0] + 1:
        raise DchError("truncated DCH header")
    end = data[0] + 1
    try:
        signature = data[1:end].decode("ascii")
    except UnicodeDecodeError:
        raise DchError("invalid DCH signature") from None
    if signature == "DTSCHEM":
        if len(data) < end + 3:
            raise DchError("missing DCH format version")
        version = int.from_bytes(data[end:end+3], "big") - 1_000_000
        end += 3
    elif signature in _LEGACY_HEADERS:
        version = _LEGACY_HEADERS[signature]
    else:
        raise UnsupportedVersionError(f"unsupported DCH signature {signature!r}; minimum is DTSCHEM2.22/schema {MIN_VERSION}",
                                      reason='format')
    if not DCH.supports_read(version):
        raise UnsupportedVersionError(f"DCH schema {version} is outside supported range {MIN_VERSION}..{MAX_KNOWN_VERSION}",
                                      version=version)
    return Header(signature, version, end)


class Cursor(BinaryReader):
    error_type = DchError

    def __init__(self, data: bytes, *, source: str | None = None, ansi_encoding="cp1252"):
        self.header = read_header(data)
        super().__init__(data, offset=self.header.body_offset,
                         unicode_text=self.header.unicode_text, source=source,
                         ansi_encoding=ansi_encoding)
