"""PCB file and buffer I/O over one searchable editable board model."""
import codecs
from pathlib import Path

from ...common.asc import dumps as asc_text
from ...common.conversion import import_diagnostics, export_diagnostics, _set_import_format
from ...common.document_families import input_identity, model_identity
from ...common.errors import UnsupportedFileError
from ...common.text.windows_1252 import encode as ansi_bytes
from .capabilities import format_capabilities
from .errors import PcbError
from .import_context import resolve_import_context
from .export_view import prepare_export


def _input(data, format, *, context, source=None, encoding=None):
    identity = input_identity(data)
    key = format.lower().lstrip('.') if format is not None else identity.format
    _set_import_format(key)
    if identity.family not in (None, 'pcb'):
        raise UnsupportedFileError(format=key, family=identity.family,
                                   version=identity.version, reason='family')
    capabilities = format_capabilities(key) if key is not None else None
    if capabilities is None:
        raise UnsupportedFileError(family=identity.family, version=identity.version)
    version = identity.version
    if key != identity.format:
        version = None  # An explicit override must be validated by that decoder.
    if key == 'dipxml' and version is not None:
        version = '.'.join(version.split('.')[:2])
    if version is not None and not capabilities.supports_read(version):
        raise UnsupportedFileError(f'unsupported {key.upper()} input version {identity.version!r}',
            format=key, family='pcb', version=identity.version, reason='version')
    context = resolve_import_context(context)
    if key == 'dip':
        from .dip.decode import decode
        decoded = decode(data, source=source, ansi_encoding=encoding or 'cp1252')
    elif key == 'asc':
        from .asc.core import prepare_core
        decoded = prepare_core(data, source=source, encoding=encoding)
    else:
        if encoding is not None:
            raise TypeError('XML input uses the encoding in its declaration')
        from .dipxml.read import prepare
        decoded = prepare(data, source=source, context=context)
    from .assembly.assemble import assemble_core
    from .assembly.routing import assemble_routing
    from .assembly.board_rules import assemble_rules
    from .assembly.graphics import assemble_graphics
    core = assemble_core(decoded, context=context)
    routed = assemble_routing(decoded, core)
    rules = assemble_rules(decoded, routed)
    return assemble_graphics(decoded, rules).document


@import_diagnostics()
def parse(data, *, format=None, context=None, source=None, report=None, label=None, encoding=None):
    """Detect buffer content and import the current searchable PCB model."""
    return _input(data, format, context=context, source=source, encoding=encoding)


@import_diagnostics()
def parse_source(data, *, format=None, context=None, source=None, report=None, label=None, encoding=None):
    """Inspect text syntax; binary input already returns the current model."""
    identity = input_identity(data)
    key = format.lower().lstrip('.') if format is not None else identity.format
    _set_import_format(key)
    if key is None:
        raise UnsupportedFileError(family=identity.family, version=identity.version)
    format_capabilities(key)
    if key == 'dip':
        return _input(data, key, context=context, source=source, encoding=encoding)
    if context is not None:
        raise TypeError('text source inspection does not use an import context')
    if key == 'asc':
        from ...common import asc
        from ..model.document import Document
        if isinstance(data, str):
            if encoding is not None:
                raise TypeError('ASC encoding selects how a byte buffer is decoded')
            return asc.loads(data, source=source, document_factory=Document)
        return asc.loads_bytes(data, source=source, encoding=encoding, document_factory=Document)
    if encoding is not None:
        raise TypeError('XML input uses the encoding in its declaration')
    from .dipxml.syntax import loads
    return loads(data, source=source)


@import_diagnostics()
def read(path, *, format=None, context=None, report=None, label=None, encoding=None):
    """Read exactly one supplied file; its suffix does not select the reader."""
    path = Path(path)
    return _input(path.read_bytes(), format, context=context, source=str(path), encoding=encoding)


@import_diagnostics()
def read_source(path, *, format=None, context=None, report=None, label=None, encoding=None):
    path = Path(path)
    return parse_source(path.read_bytes(), format=format, context=context, source=str(path), encoding=encoding)


def _output(document, format, version):
    key = format.lower().lstrip('.')
    identity = model_identity(document)
    if identity.family != 'pcb':
        raise UnsupportedFileError(format=key, family=identity.family, version=version, reason='family')
    if document.representation != 'pcb':
        raise PcbError('PCB output requires the editable model; import source syntax with parse() first')
    return key, format_capabilities(key).output_version(version)


@export_diagnostics()
def project(document, *, format, version=None, context=None, report=None, label=None, encoding=None):
    """Create a detached text-format tree using the same output policy as I/O."""
    key, version = _output(document, format, version)
    if key == 'dip':
        raise ValueError('DIP has no text tree; use serialize()')
    if key != 'asc' and encoding is not None:
        raise TypeError('XML output is UTF-8; encoding is an ASC option')
    view, context = prepare_export(document, context=context, report=report, destination=key)
    if key == 'asc':
        from .asc.write import project as project_asc
        return project_asc(view, report=report, legacy_picture_files=context.legacy_picture_files,
                           encoding=encoding or 'cp1252')
    from .dipxml.write import project_document
    return project_document(view, version=version, report=report,
                            legacy_picture_files=context.legacy_picture_files)


@export_diagnostics()
def serialize(document, *, format, version=None, context=None, report=None, label=None, encoding=None):
    """Export bytes without mutating the source or depending on its input format."""
    key, version = _output(document, format, version)
    if key == 'dip':
        if encoding is not None:
            raise TypeError('encoding is an ASC output option')
        from .dip.write import encode
        return encode(document, version=version, context=context, report=report)
    output = project(document, format=key, version=version, context=context, report=report, encoding=encoding)
    if key == 'asc':
        text = asc_text(output, preserve=False)
        selected = codecs.lookup(encoding or 'cp1252').name
        return ansi_bytes(text, best_fit=False) if selected == 'cp1252' else text.encode(selected)
    from .dipxml.syntax import dumps
    return dumps(output).encode('utf-8')


@export_diagnostics()
def write(document, path, *, format=None, version=None, context=None, report=None, label=None, encoding=None):
    """Select output by suffix or override; finish conversion before opening it."""
    key = format or Path(path).suffix
    data = serialize(document, format=key, version=version, context=context, report=report, encoding=encoding)
    Path(path).write_bytes(data)
