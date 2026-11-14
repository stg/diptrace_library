"""Component-library reading, inspection, data editing and conversion."""
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
from .model import Document, new_library, new_component, new_part, new_pin, new_drawing, new_pattern, new_pad, new_group, new_pattern_drawing, new_internal_connection
from .model.schema import component_schema


format_capabilities = _for_family(_format_capabilities, 'component')
parse = _for_family(_parse, 'component')
parse_source = _for_family(_parse_source, 'component')
read = _for_family(_read, 'component')
read_source = _for_family(_read_source, 'component')
serialize = _for_family(_serialize, 'component')
write = _for_family(_write, 'component')
new_document = new_library

__all__ = ['format_capabilities', 'parse', 'parse_source', 'read', 'read_source', 'serialize', 'write', 'project', 'ImportContext', 'ExportContext', 'Document', 'component_schema', 'new_document', 'new_library', 'new_component', 'new_part', 'new_pin', 'new_drawing', 'new_pattern', 'new_pad', 'new_group', 'new_pattern_drawing', 'new_internal_connection']
