"""Public document API. Format adapters populate our own ordered editable model."""
from pathlib import Path
from .common.capabilities import FormatCapabilities
from .common.refdes import RefDesFamily, split_refdes
from .schematic.formats.capabilities import format_capabilities

from .schematic.model.document import (Document)
from .common.model import (Element, IncompleteDocumentError, SourceSpan, Value)
from .schematic.formats.asc.syntax import (loads as parse_asc, read as read_asc)
from .schematic.formats.dchxml.syntax import (loads as parse_dchxml, read as read_dchxml)
from .common.references import (References, Reference, ReferenceError, UnresolvedReference, Index, Key, Property, Guard, OrdinalGuard, Segment)
from .common.geometry import (Bounds, circular_arc_bounds, ellipse_points)
from .schematic.layout.geometry import (symbol_bounds, pattern_bounds)
from .schematic.editing.edit import (coalesce_routes, RemovedRoutePoint)
from .schematic.formats.export_context import (ExportContext, AscExportContext, DchExportContext, DchXmlExportContext)
from .schematic.formats.path_variables import (PathVariables)
from .schematic.model.new import (new_schematic)
from .schematic.model.objects import (new_symbol, new_pin, new_schematic_shape, new_net, new_wire)
from .schematic.model.catalogue import (schematic_schema)
from .common.conversion import (ConversionNotice, ConversionWarning, ConversionReport, ImportReport, ExportReport, import_diagnostics, export_diagnostics)
from .schematic.formats.import_context import (ImportContext, resolve_import_context)


def _read_dch(path, **options):
    from .schematic.formats.dch.read import (read as read_dch)
    return read_dch(path, **options)


@import_diagnostics('dch')
def parse_dch(data, *, report=None, label=None, **options) -> Document:
    """Decode a binary buffer; label attributes its report diagnostics."""
    from .schematic.formats.dch.read import (loads)
    return loads(data, **options)


@import_diagnostics()
def parse_source(data, *, format: str, report=None, label=None, **options) -> Document:
    """Parse a source view for explicit format-level investigation."""
    key = format.lower().lstrip('.')
    if key == 'dch':
        return parse_dch(data, **options)
    if key == 'dchxml':
        return parse_dchxml(data, **options)
    if key == 'asc':
        if isinstance(data, str):
            return parse_asc(data, **options)
        from .schematic.formats.asc.syntax import (loads_bytes)
        return loads_bytes(data, **options)
    raise ValueError(f'no parser registered for {key!r}')


@import_diagnostics()
def parse(data, *, format: str, context=None, report=None, label=None, **options) -> Document:
    """Import an in-memory design into the common searchable/editable model."""
    key = format.lower().lstrip('.')
    context = resolve_import_context(context)
    document = parse_source(data, format=format, **options, **({'context': context} if key == 'dch' else {}))
    return document.as_schematic() if key in ('asc', 'dchxml') else document


_READERS = {"asc": read_asc, "dch": _read_dch, "dchxml": read_dchxml}
_WRITERS = {"asc": lambda doc, path, **options: doc.save_asc(path, **options),
            "dch": lambda doc, path, **options: doc.save_dch(path, **options),
            "dchxml": lambda doc, path, **options: doc.save_dchxml(path, **options)}


def register_reader(format: str, reader):
    """Add a format adapter without changing the document model."""
    key = format.lower().lstrip(".")
    if not key or not callable(reader):
        raise ValueError("reader registration needs a format name and callable")
    if key in _READERS:
        raise ValueError(f"reader already registered: {key}")
    _READERS[key] = reader


def register_writer(format: str, writer):
    key = format.lower().lstrip(".")
    if not key or not callable(writer):
        raise ValueError("writer registration needs a format name and callable")
    if key in _WRITERS:
        raise ValueError(f"writer already registered: {key}")
    _WRITERS[key] = writer


@import_diagnostics()
def read_source(path, *, format: str | None = None, report=None, label=None, **options) -> Document:
    """Read a format's source representation for inspection or exact re-emission.

    DCH already uses the shared model. ASC/XML retain their public syntax tree;
    use read() for ordinary format-independent schematic work.
    """
    key = (format or Path(path).suffix).lower().lstrip(".")
    if key not in _READERS:
        raise ValueError(f"no reader registered for {key!r}")
    return _READERS[key](path, **options)


@import_diagnostics()
def read(path, *, format: str | None = None, context=None, report=None, label=None, **options) -> Document:
    """Import a schematic into the same searchable, editable model in every format.

    Unsupported semantic data fails explicitly; read_source() remains available
    for inspecting it without normalization. Registered adapters which already
    return their own document representation pass through unchanged.
    """
    key = (format or Path(path).suffix).lower().lstrip('.')
    context = resolve_import_context(context)
    document = read_source(path, format=format, **options, **({'context': context} if key == 'dch' else {}))
    if key in ('asc', 'dchxml'):
        return document.as_schematic()
    return document


@export_diagnostics()
def write(document: Document, path, *, format: str | None = None, context=None, report=None, label=None, **options):
    key = (format or Path(path).suffix).lower().lstrip(".")
    if key not in _WRITERS:
        raise ValueError(f"no writer registered for {key!r}")
    if context is not None:
        options['context'] = context
    if report is not None:
        options['report'] = report
    return _WRITERS[key](document, path, **options)


@export_diagnostics()
def serialize(document: Document, *, format: str, context=None, report=None, label=None, **options) -> bytes:
    """Export an in-memory design; every format returns bytes.

    Uses the same adapters, options and report contract as write().
    """
    key = format.lower().lstrip('.')
    if key not in ('dch', 'asc', 'dchxml'):
        raise ValueError(f'no serializer registered for {key!r}')
    return getattr(document, 'to_'+key+'_bytes')(context=context, report=report, **options)


__all__ = ["FormatCapabilities", "format_capabilities", "RefDesFamily", "split_refdes",
           "Document", "Element", "Value", "SourceSpan", "IncompleteDocumentError",
           "References", "Reference", "ReferenceError", "UnresolvedReference", "Index", "Key", "Property", "Guard", "OrdinalGuard", "Segment",
           "Bounds", "circular_arc_bounds", "ellipse_points", "symbol_bounds", "pattern_bounds",
           "coalesce_routes", "RemovedRoutePoint",
           "ExportContext", "AscExportContext", "DchExportContext", "DchXmlExportContext", "ImportContext", "PathVariables",
           "ConversionNotice", "ConversionWarning", "ConversionReport", "ImportReport", "ExportReport",
           "read", "read_source", "parse", "parse_source", "write", "serialize", "register_reader", "register_writer", "read_asc", "parse_asc", "parse_dch",
           "read_dchxml", "parse_dchxml", "new_schematic", "new_symbol", "new_pin",
           "new_schematic_shape", "new_net", "new_wire", "schematic_schema"]
