"""Decode named current and compatibility fields before library normalization."""
from dataclasses import dataclass

from ....common.catalog_codec import read_categories
from ....common.library_binary import LibraryHeader
from ....common.model import Element
from ....common.library_graphics import read_library_graphics
from .reader import Reader
from .parameters import read_parameters
from .pads import read_pads
from .metadata import read_metadata


@dataclass(frozen=True)
class DecodedLibrary:
    header: LibraryHeader
    root: Element
    identity_word: int | None


def decode(data, *, source=None, ansi_encoding='cp1252'):
    reader = Reader(data, source=source, ansi_encoding=ansi_encoding)
    header = reader.header
    root = Element('Library')
    root.add('Name', header.name)
    root.add('Hint', header.hint)
    identity = int.from_bytes(reader.take(4), 'little') if header.version >= 26 else None
    if header.version >= 18:
        read_categories(reader, root)
    else:
        root.add('Categories')
    patterns = root.add('Patterns')
    for _ in range(header.entry_count):
        pattern = reader.add(patterns, 'Pattern')
        read_parameters(reader, pattern)
        read_pads(reader, pattern)
        read_library_graphics(reader, pattern, physical_coordinates=header.version >= 20,
            drawing_pad_links=header.version >= 25, extended_fonts=header.version >= 26)
        read_metadata(reader, pattern)
    if reader.pos != len(reader.data):
        raise reader.error_type(f'unconsumed library data at byte {reader.pos:#x}')
    return DecodedLibrary(header, root, identity)
