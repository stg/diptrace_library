"""Component-library header and cursor; not a complete document decoder."""
from ....common.binary import BinaryReader
from ....common.library_binary import read_library_header
from ..revisions import BINARY_READ_VERSIONS


KNOWN_VERSIONS = BINARY_READ_VERSIONS


class ComponentError(ValueError):
    pass


class Cursor(BinaryReader):
    error_type = ComponentError

    def __init__(self, data, *, source=None, ansi_encoding='cp1252'):
        super().__init__(data, unicode_text=False, ansi_encoding=ansi_encoding, ansi_length_bytes=1)
        self.source = source
        self.header = read_library_header(self, signature=b'DTELIB', versions=KNOWN_VERSIONS,
            unicode_since=24, count_first=False, format='eli', family='component')
