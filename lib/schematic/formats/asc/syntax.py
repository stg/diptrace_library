"""Schematic ASC syntax entry points over the shared ASC codec."""
from pathlib import Path

from ....common import asc
from ...model.document import Document
from ...model.refs import bind_schematic_references


def _bind(document):
    bind_schematic_references(document)
    return document


def loads(text, *, source=None, retain_source=True):
    return _bind(asc.loads(text, source=source, document_factory=Document, retain_source=retain_source))


def loads_bytes(data, *, source=None, encoding=None, retain_source=True):
    return _bind(asc.loads_bytes(data, source=source, encoding=encoding, document_factory=Document,
                                retain_source=retain_source))


def read(path, *, encoding=None):
    path = Path(path)
    return loads_bytes(path.read_bytes(), source=str(path), encoding=encoding)


def dumps(document, *, preserve=True):
    if document.metadata.get('asc_layout') == 'schematic-46':
        from .layout import dumps as layout_dumps
        return layout_dumps(document)
    return asc.dumps(document, preserve=preserve)
