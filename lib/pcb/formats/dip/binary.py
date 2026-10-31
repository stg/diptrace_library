"""DIP header recognition and scalar cursor.

Recognizing a header is distinct from having a complete adapter for its body.
The public format registry advertises only completed document adapters.
"""
from dataclasses import dataclass

from ....common.binary import BinaryReader
from ..errors import PcbError
from ..capabilities import DIP


MIN_VERSION = min(DIP.read_versions)
MAX_KNOWN_VERSION = max(DIP.read_versions)
_LEGACY_HEADERS = {'DTBOARD2.2': 31, 'DTBOARD2.21': 32, 'DTBOARD2.22': 33}


DipError = PcbError


class UnsupportedVersionError(DipError):
    pass


@dataclass(frozen=True)
class Header:
    signature: str
    version: int
    body_offset: int

    @property
    def unicode_text(self):
        return self.version >= 38


def read_header(data):
    if not data or len(data) < data[0]+1:
        raise DipError('truncated DIP header')
    end = data[0]+1
    try:
        signature = data[1:end].decode('ascii')
    except UnicodeDecodeError:
        raise DipError('invalid DIP signature') from None
    if signature == 'DTBOARD':
        if len(data) < end+3:
            raise DipError('missing DIP format version')
        version = int.from_bytes(data[end:end+3], 'big')-1_000_000
        end += 3
    elif signature in _LEGACY_HEADERS:
        version = _LEGACY_HEADERS[signature]
    else:
        raise UnsupportedVersionError(f'unsupported DIP signature {signature!r}')
    if not MIN_VERSION <= version <= MAX_KNOWN_VERSION:
        raise UnsupportedVersionError(f'DIP schema {version} is outside recognized range '
                                      f'{MIN_VERSION}..{MAX_KNOWN_VERSION}')
    return Header(signature, version, end)


class Cursor(BinaryReader):
    error_type = DipError

    def __init__(self, data, *, source=None, ansi_encoding='cp1252'):
        self.header = read_header(data)
        super().__init__(data, offset=self.header.body_offset,
                         unicode_text=self.header.unicode_text,
                         source=source, ansi_encoding=ansi_encoding)
