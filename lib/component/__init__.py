"""Component-library conversion entry points; adapters are not available yet.

The functions use the generic library signatures with the component family
selected. Conversion and capability queries raise UnsupportedFileError (ValueError).
"""
from .. import (
    _for_family, format_capabilities as _capabilities, parse as _parse,
    read as _read, serialize as _serialize, write as _write,
)

format_capabilities = _for_family(_capabilities, 'component')
parse = _for_family(_parse, 'component')
read = _for_family(_read, 'component')
serialize = _for_family(_serialize, 'component')
write = _for_family(_write, 'component')

__all__ = ['format_capabilities', 'parse', 'read', 'serialize', 'write']
