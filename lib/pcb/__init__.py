"""PCB conversion entry points; adapters are not available yet.

The functions use the generic library signatures with the PCB family selected.
Conversion and capability queries currently raise UnsupportedFileError (ValueError).
"""
from .. import (
    _for_family, format_capabilities as _capabilities, parse as _parse,
    read as _read, serialize as _serialize, write as _write,
)

format_capabilities = _for_family(_capabilities, 'pcb')
parse = _for_family(_parse, 'pcb')
read = _for_family(_read, 'pcb')
serialize = _for_family(_serialize, 'pcb')
write = _for_family(_write, 'pcb')

__all__ = ['format_capabilities', 'parse', 'read', 'serialize', 'write']
