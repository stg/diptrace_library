"""DCH byte cursor and version policy, independent of the document model."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


MIN_VERSION = 29
MAX_KNOWN_VERSION = 52
_LEGACY_HEADERS = {"DTSCHEM2.22": 29, "DTSCHEM2.21": 28, "DTSCHEM2.2": 27}


class DchError(ValueError):
    pass


class UnsupportedVersionError(DchError):
    pass


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
        raise UnsupportedVersionError(f"unsupported DCH signature {signature!r}; minimum is DTSCHEM2.22/schema {MIN_VERSION}")
    if not MIN_VERSION <= version <= MAX_KNOWN_VERSION:
        raise UnsupportedVersionError(f"DCH schema {version} is outside supported range {MIN_VERSION}..{MAX_KNOWN_VERSION}")
    return Header(signature, version, end)


class Cursor:
    def __init__(self, data: bytes, *, source: str | None = None, ansi_encoding="cp1252"):
        self.data, self.source = data, source
        self.header = read_header(data)
        self.pos = self.header.body_offset
        self.ansi_encoding = ansi_encoding

    def take(self, length):
        if length < 0 or self.pos + length > len(self.data):
            raise DchError(f"truncated field at byte {self.pos:#x}: need {length}, have {len(self.data)-self.pos}")
        raw = self.data[self.pos:self.pos+length]
        self.pos += length
        return raw

    def integer(self):
        return int.from_bytes(self.take(3), "big") - 1_000_000

    def number(self):
        # Decode fixed-point units with integer arithmetic. Constructing the
        # decimal directly avoids rounding through the caller's Decimal context.
        units = int.from_bytes(self.take(4), "big") - 1_000_000_000
        return Decimal(f"{units}e-4")

    def boolean(self):
        start = self.pos
        value = self.take(1)[0]
        if value not in (0, 1):
            raise DchError(f"invalid boolean {value} at byte {start:#x}")
        return bool(value)

    def color(self):
        # COLORREF-style RGB byte order, without the integer codec's bias.
        return int.from_bytes(self.take(3), "little")

    def text(self):
        if self.header.unicode_text:
            length = int.from_bytes(self.take(2), "big")
            # Text stores code units without requiring valid surrogate pairs.
            # Preserve unusual but serialized UTF-16 data exactly.
            return self.take(length*2).decode("utf-16-be", errors="surrogatepass")
        length = self.integer()
        if length < 0:
            raise DchError(f"negative string length at byte {self.pos-3:#x}")
        raw = self.take(length)
        if self.ansi_encoding.lower().replace('_', '-') in ('cp1252', 'windows-1252'):
            from ....common.text.windows_1252 import (decode)
            return decode(raw)
        return raw.decode(self.ansi_encoding)

    def count(self, label):
        value = self.integer()
        if value < 0 or value > len(self.data) - self.pos:
            raise DchError(f"invalid {label} count {value} at byte {self.pos-3:#x}")
        return value
