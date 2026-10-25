"""Public document API. Format adapters populate our own ordered editable model."""
from pathlib import Path
from functools import wraps
from .common.capabilities import FormatCapabilities
from .common.errors import UnsupportedFileError
from .common.document_families import (
    FORMAT_FAMILIES, DocumentIdentity, document_family, family_name,
    input_identity, model_identity,
)
from .common.refdes import RefDesFamily, split_refdes
from .schematic.formats.capabilities import format_capabilities as _schematic_capabilities

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


def _unsupported(format, identity, *, version=None):
    raise UnsupportedFileError(format=format, family=identity.family,
                               version=identity.version if version is None else version,
                               reason='family' if identity.family not in (None, 'schematic') else 'format')


def _input_family(data, format, family):
    selected = family_name(family) if family is not None else None
    detected = input_identity(data)
    identity = detected if selected is None else DocumentIdentity(selected, detected.version)
    if identity.family != 'schematic' or format not in ('asc', 'dch', 'dchxml'):
        _unsupported(format, identity)
    return identity.family


def _output_family(document, format, family, *, version=None):
    identity = model_identity(document) if family is None else DocumentIdentity(family_name(family))
    if identity.family != 'schematic':
        _unsupported(format, identity, version=version)
    return identity.family


def format_capabilities(format, *, family=None):
    """Return adapter support; explicit family selection disambiguates ASC."""
    key = format.lower().lstrip('.')
    if family is None and key == 'asc':
        raise ValueError('ASC capabilities require an explicit document family')
    selected = family_name(family) if family is not None else FORMAT_FAMILIES.get(key)
    if selected != 'schematic' or key not in ('asc', 'dch', 'dchxml'):
        _unsupported(key, DocumentIdentity(selected))
    return _schematic_capabilities(key)


def _for_family(operation, family):
    """Bind the generic conversion surface for a family's package entry point."""
    @wraps(operation)
    def run(*args, **options):
        return operation(*args, family=family, **options)
    return run


def _read_dch(path, **options):
    from .schematic.formats.dch.read import (read as read_dch)
    return read_dch(path, **options)


@import_diagnostics('dch')
def parse_dch(data, *, report=None, label=None, **options) -> Document:
    """Decode a binary buffer; label attributes its report diagnostics."""
    from .schematic.formats.dch.read import (loads)
    return loads(data, **options)


@import_diagnostics()
def parse_source(data, *, format: str, family: str | None = None, report=None, label=None, **options) -> Document:
    """Parse a source view for explicit format-level investigation."""
    key = format.lower().lstrip('.')
    _input_family(data, key, family)
    return _load_source(data, key, **options)


def _load_source(data, key, **options):
    if key == 'dch':
        return parse_dch(data, **options)
    if key == 'dchxml':
        return parse_dchxml(data, **options)
    if key == 'asc':
        if isinstance(data, str):
            return parse_asc(data, **options)
        from .schematic.formats.asc.syntax import (loads_bytes)
        return loads_bytes(data, **options)


@import_diagnostics()
def parse(data, *, format: str, family: str | None = None, context=None, report=None, label=None, **options) -> Document:
    """Import an in-memory design into the common searchable/editable model."""
    key = format.lower().lstrip('.')
    _input_family(data, key, family)
    context = resolve_import_context(context)
    document = _load_source(data, key, **options, **({'context': context} if key == 'dch' else {}))
    return document.as_schematic() if key in ('asc', 'dchxml') else document


_READERS = {"asc": read_asc, "dch": _read_dch, "dchxml": read_dchxml}
_WRITERS = {"asc": lambda doc, path, **options: doc.save_asc(path, **options),
            "dch": lambda doc, path, **options: doc.save_dch(path, **options),
            "dchxml": lambda doc, path, **options: doc.save_dchxml(path, **options)}
_BUILTIN_READERS = _READERS.copy()
_BUILTIN_WRITERS = _WRITERS.copy()


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
def read_source(path, *, format: str | None = None, family: str | None = None, report=None, label=None, **options) -> Document:
    """Read a format's source representation for inspection or exact re-emission.

    DCH already uses the shared model. ASC/XML retain their public syntax tree;
    use read() for ordinary format-independent schematic work.
    """
    key = (format or Path(path).suffix).lower().lstrip(".")
    return _read_file(path, key, family, options)


def _read_file(path, key, family, options, *, normalize=False, context=None):
    reader = _READERS.get(key)
    if reader is not None and reader is not _BUILTIN_READERS.get(key):
        if family is not None:
            family_name(family)
        if normalize:
            resolved = resolve_import_context(context)
            if key == 'dch':
                options['context'] = resolved
        return reader(path, **options)
    data = Path(path).read_bytes()
    _input_family(data, key, family)
    if normalize:
        resolved = resolve_import_context(context)
        if key == 'dch':
            options['context'] = resolved
    return _load_source(data, key, source=str(path), **options)


@import_diagnostics()
def read(path, *, format: str | None = None, family: str | None = None, context=None, report=None, label=None, **options) -> Document:
    """Import a schematic into the same searchable, editable model in every format.

    Unsupported semantic data fails explicitly; read_source() remains available
    for inspecting it without normalization. Registered adapters which already
    return their own document representation pass through unchanged.
    """
    key = (format or Path(path).suffix).lower().lstrip('.')
    document = _read_file(path, key, family, options, normalize=True, context=context)
    if key in ('asc', 'dchxml'):
        return document.as_schematic()
    return document


@export_diagnostics()
def write(document: Document, path, *, format: str | None = None, family: str | None = None, context=None, report=None, label=None, **options):
    key = (format or Path(path).suffix).lower().lstrip(".")
    writer = _WRITERS.get(key)
    if writer is None or writer is _BUILTIN_WRITERS.get(key):
        selected = _output_family(document, key, family, version=options.get('version'))
    else:
        selected = family_name(family) if family is not None else None
    if key not in _WRITERS:
        _unsupported(key, DocumentIdentity(selected), version=options.get('version'))
    if context is not None:
        options['context'] = context
    if report is not None:
        options['report'] = report
    return _WRITERS[key](document, path, **options)


@export_diagnostics()
def serialize(document: Document, *, format: str, family: str | None = None, context=None, report=None, label=None, **options) -> bytes:
    """Export an in-memory design; every format returns bytes.

    Uses the same adapters, options and report contract as write().
    """
    key = format.lower().lstrip('.')
    selected = _output_family(document, key, family, version=options.get('version'))
    if key not in ('dch', 'asc', 'dchxml'):
        _unsupported(key, DocumentIdentity(selected), version=options.get('version'))
    return getattr(document, 'to_'+key+'_bytes')(context=context, report=report, **options)


__all__ = ["FormatCapabilities", "format_capabilities", "document_family", "UnsupportedFileError", "RefDesFamily", "split_refdes",
           "Document", "Element", "Value", "SourceSpan", "IncompleteDocumentError",
           "References", "Reference", "ReferenceError", "UnresolvedReference", "Index", "Key", "Property", "Guard", "OrdinalGuard", "Segment",
           "Bounds", "circular_arc_bounds", "ellipse_points", "symbol_bounds", "pattern_bounds",
           "coalesce_routes", "RemovedRoutePoint",
           "ExportContext", "AscExportContext", "DchExportContext", "DchXmlExportContext", "ImportContext", "PathVariables",
           "ConversionNotice", "ConversionWarning", "ConversionReport", "ImportReport", "ExportReport",
           "read", "read_source", "parse", "parse_source", "write", "serialize", "register_reader", "register_writer", "read_asc", "parse_asc", "parse_dch",
           "read_dchxml", "parse_dchxml", "new_schematic", "new_symbol", "new_pin",
           "new_schematic_shape", "new_net", "new_wire", "schematic_schema"]
