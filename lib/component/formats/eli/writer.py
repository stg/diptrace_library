"""Standalone ELI output with independently declared component revision gates."""
import secrets

from ....common.binary_records import RecordWriter
from ....common.catalog_codec import write_categories
from ....common.errors import UnsupportedFileError
from ....common.font_codec import compatibility_size
from ..revisions import BINARY_DEFAULT_WRITE_VERSION, BINARY_WRITE_VERSIONS


class Writer(RecordWriter):
    format_name = 'ELI'

    def __init__(self, version=None, *, report=None):
        version = BINARY_DEFAULT_WRITE_VERSION if version is None else version
        if version not in BINARY_WRITE_VERSIONS:
            raise UnsupportedFileError(f'ELI output version {version} is not supported',
                format='eli', family='component', version=version, reason='version')
        super().__init__()
        self.version, self.report = version, report

    def container(self, library, count):
        signature = b'DTELIB'
        self.buffer.append(len(signature))
        self.buffer.extend(signature)
        self.integer(self.version)
        self.fields(library, 'text', 'Name Hint')
        if self.version >= 33:
            self.buffer.extend(secrets.randbits(32).to_bytes(4, 'little'))
        write_categories(self, library)
        self.rows(library.one('Subfolders'), 'Folder', 'text')
        self.integer(count)

    def field_value(self, parent, name, codec, value):
        if name == 'Group' and codec == 'integer' and parent.schema is not None and 'GroupId' in parent.schema.fields:
            return parent['GroupId']
        if name in ('FontSize', 'NameFontSize') and codec == 'integer':
            return compatibility_size(value)
        return super().field_value(parent, name, codec, value)
