"""Pattern-library conversion entry points; adapters are not available yet.

The functions use the generic library signatures with the pattern family
selected. Conversion and capability queries raise UnsupportedFileError (ValueError).
"""
from .. import (
    _for_family, format_capabilities as _capabilities, parse as _parse,
    read as _read, serialize as _serialize, write as _write,
)

format_capabilities = _for_family(_capabilities, 'pattern')
parse = _for_family(_parse, 'pattern')
read = _for_family(_read, 'pattern')
serialize = _for_family(_serialize, 'pattern')
write = _for_family(_write, 'pattern')

__all__ = ['format_capabilities', 'parse', 'read', 'serialize', 'write']
