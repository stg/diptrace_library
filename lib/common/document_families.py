"""Document identity from public signatures, declarations and current models.

Identity recognition does not imply that a document adapter is available.
"""
from dataclasses import dataclass
import re
from xml.parsers import expat

from .errors import UnsupportedFileError


FAMILIES = ('schematic', 'pcb', 'component', 'pattern')
FORMAT_FAMILIES = {
    'dch': 'schematic', 'dchxml': 'schematic',
    'dip': 'pcb', 'dipxml': 'pcb',
    'eli': 'component', 'elixml': 'component',
    'lib': 'pattern', 'libxml': 'pattern',
}
_NATIVE = {b'DTSCHEM': 'schematic', b'DTBOARD': 'pcb',
           b'DTELIB': 'component', b'DTCLIB': 'pattern'}
_LEGACY = {b'DTSCHEM2.2': ('schematic', 27),
           b'DTSCHEM2.21': ('schematic', 28),
           b'DTSCHEM2.22': ('schematic', 29),
           b'DTBOARD2.2': ('pcb', 31),
           b'DTBOARD2.21': ('pcb', 32),
           b'DTBOARD2.22': ('pcb', 33)}
_ASC_TYPES = {'DipTrace-Schematic': 'schematic', 'DipTrace-PCBN': 'pcb',
              'DipTrace-ElementLibrary': 'component', 'DipTrace-ComLibrary': 'pattern'}
_XML_TYPES = {('Source', 'DipTrace-Schematic'): 'schematic',
              ('Source', 'DipTrace-PCB'): 'pcb',
              ('Library', 'DipTrace-ComponentLibrary'): 'component',
              ('Library', 'DipTrace-PatternLibrary'): 'pattern'}
_ASC_TOKENS = re.compile(r'\(|\)|"[^"]*"|[^\s()"]+', re.DOTALL)


@dataclass(frozen=True)
class DocumentIdentity:
    family: str | None = None
    version: int | str | None = None


def family_name(family):
    if not isinstance(family, str):
        raise TypeError('document family must be a string')
    selected = family.lower()
    if selected not in FAMILIES:
        raise ValueError(f'unknown document family: {family!r}')
    return selected


def _asc_identity(text):
    depth = 0
    header = None
    for match in _ASC_TOKENS.finditer(text):
        token = match.group()
        if token == '(':
            depth += 1
            if depth == 1:
                header = []
        elif token == ')':
            if depth == 1 and header and header[0] == 'Source':
                values = [value[1:-1] if value.startswith('"') else value
                          for value in header[1:]]
                version = values[1] if len(values) > 1 else None
                if version is not None and version.isascii() and version.isdecimal():
                    version = int(version)
                return DocumentIdentity(_ASC_TYPES.get(values[0]) if values else None, version)
            depth -= 1
        elif depth == 1:
            header.append(token)
    return DocumentIdentity()


def _xml_identity(data):
    class RootFound(Exception):
        pass

    identity = DocumentIdentity()

    def start(name, attributes):
        nonlocal identity
        identity = DocumentIdentity(_XML_TYPES.get((name, attributes.get('Type'))),
                                    attributes.get('Version'))
        raise RootFound

    parser = expat.ParserCreate()
    parser.StartElementHandler = start
    try:
        parser.Parse(data, False)
    except (RootFound, expat.ExpatError):
        pass
    return identity


def input_identity(data):
    """Recognize identity without validating the supported adapter's document."""
    if isinstance(data, (bytes, bytearray, memoryview)):
        data = bytes(data)
        if data and len(data) >= data[0] + 1:
            end = data[0] + 1
            signature = data[1:end]
            if signature in _LEGACY:
                return DocumentIdentity(*_LEGACY[signature])
            if signature in _NATIVE:
                version = (int.from_bytes(data[end:end+3], 'big') - 1_000_000
                           if len(data) >= end+3 else None)
                return DocumentIdentity(_NATIVE[signature], version)
        stripped = data.lstrip(b'\xef\xbb\xbf \t\r\n')
        if stripped.startswith(b'<') or data.startswith((b'\xff\xfe', b'\xfe\xff')):
            return _xml_identity(data)
        # Header type names and syntax punctuation are ASCII in every supported
        # ASC encoding. The actual adapter remains responsible for decoding.
        text = data.decode('latin-1')
    elif isinstance(data, str):
        text = data
        if text.lstrip('\ufeff \t\r\n').startswith('<'):
            return _xml_identity(text)
    else:
        raise TypeError('design input must be text or a byte buffer')
    return _asc_identity(text)


def model_identity(document):
    """Use current representation or declarations, never provenance metadata."""
    representation = document.representation
    if representation in FAMILIES:
        return DocumentIdentity(representation)
    for node in document.root.children():
        if node.kind == 'Source' and node.values:
            return DocumentIdentity(_ASC_TYPES.get(node.values[0]),
                                    node.values[1] if len(node.values) > 1 else None)
        if node.kind in ('Source', 'Library'):
            return DocumentIdentity(_XML_TYPES.get((node.kind, node.scalar('Type'))),
                                    node.scalar('Version'))
    return DocumentIdentity()


def document_family(document):
    """Return the current document family, or fail when it cannot be identified."""
    identity = model_identity(document)
    if identity.family is None:
        raise UnsupportedFileError(version=identity.version)
    return identity.family
