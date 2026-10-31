"""Named PCB binary record reader used by the versioned document decoder."""
from ....common.binary_records import RecordReader
from .binary import Cursor


class Reader(RecordReader, Cursor):
    source_format = 'dip'
