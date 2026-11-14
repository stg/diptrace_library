"""Named standalone binary output over the shared scalar encodings."""
import secrets

from ....common.binary_records import RecordWriter
from ....common.errors import UnsupportedFileError
from ....common.font_codec import compatibility_size
from ..revisions import BINARY_WRITE_VERSIONS,BINARY_DEFAULT_WRITE_VERSION


class Writer(RecordWriter):
    format_name='LIB'

    def __init__(self,version=None,*,report=None):
        version=BINARY_DEFAULT_WRITE_VERSION if version is None else version
        if version not in BINARY_WRITE_VERSIONS:
            raise UnsupportedFileError(f'LIB output version {version} is not supported',
                format='lib',family='pattern',version=version,reason='version')
        super().__init__()
        self.version,self.report=version,report

    def header(self,library,count):
        signature=b'DTCLIB'
        self.buffer.append(len(signature))
        self.buffer.extend(signature)
        self.integer(self.version)
        self.integer(count)
        self.fields(library,'text','Name Hint')
        if self.version >= 26:
            # This word changes on every ordinary native save/export. It is
            # generated output bookkeeping, never an editing-model identity.
            self.buffer.extend(secrets.randbits(32).to_bytes(4,'little'))

    def field_value(self,parent,name,codec,value):
        if name=='Group' and codec=='integer' and parent.schema is not None and 'GroupId' in parent.schema.fields:
            return parent['GroupId']
        if name=='FontSize' and codec=='integer':
            return compatibility_size(value)
        return super().field_value(parent,name,codec,value)
