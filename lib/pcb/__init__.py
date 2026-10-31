"""PCB document reading, inspection, editing and conversion."""
from .. import (
    _for_family, format_capabilities as _capabilities, parse as _parse,
    parse_source as _parse_source, read as _read, read_source as _read_source,
    serialize as _serialize, write as _write,
)
from .formats.import_context import ImportContext
from .formats.export_context import ExportContext
from .model.document import Document
from .model.catalogue import pcb_schema
from .model.objects import (
    new_document, new_component, new_pad, new_user_field, new_pattern_drawing,
    new_net, new_point, new_trace, new_layer, new_via_style, new_net_class,
    new_pair, new_removed_pair,
)


format_capabilities = _for_family(_capabilities, 'pcb')
parse = _for_family(_parse, 'pcb')
parse_source = _for_family(_parse_source, 'pcb')
read = _for_family(_read, 'pcb')
read_source = _for_family(_read_source, 'pcb')
serialize = _for_family(_serialize, 'pcb')
write = _for_family(_write, 'pcb')

__all__ = [
    'format_capabilities', 'parse', 'parse_source', 'read', 'read_source', 'serialize', 'write',
    'ImportContext', 'ExportContext', 'Document', 'pcb_schema',
    'new_document', 'new_component', 'new_pad', 'new_user_field',
    'new_pattern_drawing', 'new_net', 'new_point', 'new_trace',
    'new_layer', 'new_via_style', 'new_net_class', 'new_pair', 'new_removed_pair',
]
