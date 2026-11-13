"""Schematic buffer I/O behind the shared document-family dispatcher."""
from pathlib import Path

from ..model.document import Document
from ...common.conversion import import_diagnostics, export_diagnostics, _set_import_format
from ...common.document_families import input_identity
from ...common.errors import UnsupportedFileError
from .capabilities import FORMATS
from .import_context import resolve_import_context


def format_capabilities(format):
    key = format.lower().lstrip('.')
    try:
        return FORMATS[key]
    except KeyError:
        raise UnsupportedFileError(format=key, family='schematic') from None


def _key(data, format):
    identity = input_identity(data)
    key = format.lower().lstrip('.') if format is not None else identity.format
    _set_import_format(key)
    if key not in FORMATS:
        raise UnsupportedFileError(format=key, family='schematic', version=identity.version)
    return key


def _source(data, key, **options):
    if key == 'dch':
        from .dch.read import loads
        return loads(data, **options)
    if key == 'dchxml':
        from .dchxml.syntax import loads
        return loads(data, **options)
    from .asc.syntax import loads, loads_bytes
    return loads(data, **options) if isinstance(data, str) else loads_bytes(data, **options)


@import_diagnostics()
def parse_source(data, *, format=None, source=None, report=None, label=None, **options):
    """Read an explicit source view without changing its representation."""
    key = _key(data, format)
    if key == 'dch' and options.get('context') is None:
        from dataclasses import replace
        options['context'] = replace(resolve_import_context(None), retain_source=True)
    return _source(data, key, source=source, **options)


@import_diagnostics()
def parse(data, *, format=None, context=None, source=None, report=None, label=None, **options):
    key = _key(data, format)
    resolved = resolve_import_context(context)
    if key == 'dch':
        options['context'] = resolved
    else:
        options['retain_source'] = resolved.retain_source
    document = _source(data, key, source=source, **options)
    if key == 'asc':
        from .asc.read import import_schematic
        document = import_schematic(document, _take_root=True)
    elif key == 'dchxml':
        document = document.as_schematic()
    if not resolved.retain_source and key != 'dch':
        from ...common.source_details import discard_source
        discard_source(document.root)
    return document


def _output_key(format, version):
    key = format.lower().lstrip('.')
    if key not in FORMATS:
        raise UnsupportedFileError(format=key, family='schematic', version=version)
    return key


@export_diagnostics()
def serialize(document: Document, *, format, context=None, report=None, label=None, **options):
    from ...common.unit_views import canonical
    document = canonical(document)
    key = _output_key(format, options.get('version'))
    return getattr(document, 'to_'+key+'_bytes')(context=context, report=report, **options)


@export_diagnostics()
def write(document: Document, path, *, format=None, context=None, report=None, label=None, **options):
    from ...common.unit_views import canonical
    document = canonical(document)
    key = _output_key(format or Path(path).suffix, options.get('version'))
    if context is not None:
        options['context'] = context
    if report is not None:
        options['report'] = report
    return getattr(document, 'save_'+key)(path, **options)
