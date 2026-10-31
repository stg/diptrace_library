"""Public document API. Format adapters populate our own ordered editable model."""
from pathlib import Path
from functools import wraps
from importlib import import_module
from .common.capabilities import FormatCapabilities
from .common.errors import UnsupportedFileError
from .common.document_families import (
    FORMAT_FAMILIES, DocumentIdentity, document_family, family_name,
    input_identity, model_identity,
)
from .common.refdes import RefDesFamily, split_refdes

from .schematic.model.document import (Document)
from .common.model import (Element, IncompleteDocumentError, SourceSpan, Value)
from .schematic.formats.asc.syntax import (loads as parse_asc, read as read_asc)
from .schematic.formats.dchxml.syntax import (loads as parse_dchxml, read as read_dchxml)
from .common.references import (References, Reference, ReferenceError, UnresolvedReference, Index, Key, Property, Guard, OrdinalGuard, Segment)
from .common.geometry import (Bounds, circular_arc_bounds, ellipse_points)
from .schematic.layout.geometry import (symbol_bounds, pattern_bounds)
from .schematic.editing.edit import (coalesce_routes, RemovedRoutePoint)
from .schematic.formats.export_context import (ExportContext, AscExportContext, DchExportContext, DchXmlExportContext)
from .common.path_variables import PathVariables
from .schematic.model.new import (new_schematic)
from .schematic.model.objects import (new_symbol, new_pin, new_schematic_shape, new_net, new_wire)
from .schematic.model.catalogue import (schematic_schema)
from .common.conversion import (ConversionNotice, ConversionWarning, ConversionReport, ImportReport, ExportReport, import_diagnostics, export_diagnostics, _set_import_format)
from .schematic.formats.import_context import ImportContext


# Availability is separate from content recognition and adapter version policy.
# Unpublished families remain absent until their implementation is ready.
_FAMILY_ADAPTERS = {
    'schematic': __name__+'.schematic.formats.io',
    'pcb': __name__+'.pcb.formats.io',
}


def _unsupported(format, identity, *, version=None):
    raise UnsupportedFileError(format=format, family=identity.family,
                               version=identity.version if version is None else version,
                               reason='family' if identity.family is not None
                                   and identity.family not in _FAMILY_ADAPTERS else 'format')


def _adapter(format, identity, *, version=None):
    selected = _FAMILY_ADAPTERS.get(identity.family)
    if selected is None:
        _unsupported(format, identity, version=version)
    return import_module(selected) if isinstance(selected, str) else selected


def _input_adapter(data, format, family):
    """Use explicit selection or declarations without preferring a family."""
    selected = family_name(family) if family is not None else None
    detected = input_identity(data)
    key = format.lower().lstrip('.') if format is not None else detected.format
    _set_import_format(key)
    identity = detected if selected is None else DocumentIdentity(selected, detected.version)
    adapter = _adapter(key, identity)
    if key is None:
        _unsupported(key, identity)
    try:
        adapter.format_capabilities(key)
    except UnsupportedFileError as error:
        if error.reason != 'format':
            raise
        _unsupported(key, identity)
    return key, adapter


def _output_adapter(document, format, family, *, version=None):
    actual = model_identity(document)
    identity = actual if family is None else DocumentIdentity(family_name(family))
    adapter = _adapter(format, identity, version=version)
    if actual.family is not None and identity.family != actual.family:
        raise UnsupportedFileError(format=format, family=actual.family,
                                   version=version, reason='family')
    return adapter


def format_capabilities(format, *, family=None):
    """Return adapter support; explicit family selection disambiguates ASC."""
    key = format.lower().lstrip('.')
    if family is None and key == 'asc':
        raise ValueError('ASC capabilities require an explicit document family')
    selected = family_name(family) if family is not None else FORMAT_FAMILIES.get(key)
    return _adapter(key, DocumentIdentity(selected)).format_capabilities(key)


def _for_family(operation, family):
    """Bind the generic conversion surface for a family's package entry point."""
    @wraps(operation)
    def run(*args, **options):
        return operation(*args, family=family, **options)
    return run


@import_diagnostics('dch')
def parse_dch(data, *, report=None, label=None, **options) -> Document:
    """Decode a binary buffer; label attributes its report diagnostics."""
    from .schematic.formats.dch.read import (loads)
    return loads(data, **options)


@import_diagnostics()
def parse_source(data, *, format: str | None = None, family: str | None = None, report=None, label=None, **options) -> Document:
    """Parse a source view for explicit format-level investigation."""
    key, adapter = _input_adapter(data, format, family)
    return adapter.parse_source(data, format=key, **options)


@import_diagnostics()
def parse(data, *, format: str | None = None, family: str | None = None, context=None, report=None, label=None, **options) -> Document:
    """Import an in-memory design into the common searchable/editable model."""
    key, adapter = _input_adapter(data, format, family)
    return adapter.parse(data, format=key, context=context, **options)


_READERS = {}
_WRITERS = {}


def _builtin_format(key):
    for family in _FAMILY_ADAPTERS:
        adapter = _adapter(key, DocumentIdentity(family))
        try:
            adapter.format_capabilities(key)
        except UnsupportedFileError:
            continue
        return True
    return False


def register_reader(format: str, reader):
    """Add a format adapter without changing the document model."""
    key = format.lower().lstrip(".")
    if not key or not callable(reader):
        raise ValueError("reader registration needs a format name and callable")
    if key in _READERS or _builtin_format(key):
        raise ValueError(f"reader already registered: {key}")
    _READERS[key] = reader


def register_writer(format: str, writer):
    key = format.lower().lstrip(".")
    if not key or not callable(writer):
        raise ValueError("writer registration needs a format name and callable")
    if key in _WRITERS or _builtin_format(key):
        raise ValueError(f"writer already registered: {key}")
    _WRITERS[key] = writer


@import_diagnostics()
def read_source(path, *, format: str | None = None, family: str | None = None, report=None, label=None, **options) -> Document:
    """Read a format's source representation for inspection or exact re-emission.

    DCH already uses the shared model. ASC/XML retain their public syntax tree;
    use read() for ordinary format-independent schematic work.
    """
    return _read_file(path, format, family, options)


def _read_file(path, format, family, options, *, normalize=False, context=None):
    hint = Path(path).suffix.lower().lstrip('.')
    key = format.lower().lstrip('.') if format is not None else hint
    reader = _READERS.get(key)
    if reader is not None:
        if family is not None:
            family_name(family)
        if normalize and context is not None:
            options['context'] = context
        return reader(path, **options)
    data = Path(path).read_bytes()
    key, adapter = _input_adapter(data, format, family)
    if normalize:
        return adapter.parse(data, format=key, source=str(path), context=context, **options)
    return adapter.parse_source(data, format=key, source=str(path), **options)


@import_diagnostics()
def read(path, *, format: str | None = None, family: str | None = None, context=None, report=None, label=None, **options) -> Document:
    """Detect a document's format and import its searchable, editable model.

    Unsupported semantic data fails explicitly; read_source() remains available
    for inspecting it without normalization. Registered adapters which already
    return their own document representation pass through unchanged.
    """
    return _read_file(path, format, family, options, normalize=True, context=context)


@export_diagnostics()
def write(document: Document, path, *, format: str | None = None, family: str | None = None, context=None, report=None, label=None, **options):
    key = (format or Path(path).suffix).lower().lstrip(".")
    writer = _WRITERS.get(key)
    if writer is None:
        adapter = _output_adapter(document, key, family, version=options.get('version'))
        return adapter.write(document, path, format=key, context=context, report=report, **options)
    if family is not None:
        family_name(family)
    if context is not None:
        options['context'] = context
    if report is not None:
        options['report'] = report
    return writer(document, path, **options)


@export_diagnostics()
def serialize(document: Document, *, format: str, family: str | None = None, context=None, report=None, label=None, **options) -> bytes:
    """Export an in-memory design; every format returns bytes.

    Uses the same adapters, options and report contract as write().
    """
    key = format.lower().lstrip('.')
    adapter = _output_adapter(document, key, family, version=options.get('version'))
    return adapter.serialize(document, format=key, context=context, report=report, **options)


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
