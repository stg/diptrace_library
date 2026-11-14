"""Pattern-library reading, inspection, data editing and conversion."""
from .. import (
    _for_family,
    format_capabilities as _format_capabilities,
    parse as _parse,
    parse_source as _parse_source,
    read as _read,
    read_source as _read_source,
    serialize as _serialize,
    write as _write,
)
from .formats.import_context import ImportContext
from .formats.export_context import ExportContext
from .formats.io import project
from .model import Document, new_library, new_pattern, new_pad, new_drawing, new_group, new_internal_connection
from .model.schema import pattern_schema


format_capabilities = _for_family(_format_capabilities, 'pattern')
parse = _for_family(_parse, 'pattern')
parse_source = _for_family(_parse_source, 'pattern')
read = _for_family(_read, 'pattern')
read_source = _for_family(_read_source, 'pattern')
serialize = _for_family(_serialize, 'pattern')
write = _for_family(_write, 'pattern')
new_document = new_library

__all__ = ['format_capabilities', 'parse', 'parse_source', 'read', 'read_source', 'serialize', 'write', 'project', 'ImportContext', 'ExportContext', 'Document', 'pattern_schema', 'new_document', 'new_library', 'new_pattern', 'new_pad', 'new_drawing', 'new_group', 'new_internal_connection']
