"""Decode standalone component bodies before owned-model modernization.

This internal decoder does not register public component-library support.
"""
from dataclasses import dataclass

from ....common.library_binary import LibraryHeader
from ....common.model import Element
from .containers import read_container
from .graphics import read_physical_graphics
from .metadata import read_physical_metadata, read_symbol_metadata
from .parameters import read_part_parameters
from .physical import read_physical_parameters, read_pads
from .reader import Reader
from .symbols import read_pins, read_symbol_graphics


@dataclass(frozen=True)
class DecodedLibrary:
    header: LibraryHeader
    root: Element


def read_component(reader, components):
    """Decode one component, including all parts and their physical definitions."""
    component = reader.add(components, 'Component')
    parts = reader.add(component, 'Parts')
    for _ in range(reader.count('component parts')):
        part = read_part_parameters(reader, parts)
        pattern = read_physical_parameters(reader, part, part)
        read_pads(reader, pattern)
        read_physical_graphics(reader, pattern)
        read_physical_metadata(reader, pattern)
        read_pins(reader, part)
        read_symbol_graphics(reader, part)
        read_symbol_metadata(reader, part)
    return component


def decode(data, *, source=None, ansi_encoding='cp1252'):
    reader = Reader(data, source=source, ansi_encoding=ansi_encoding)
    container = read_container(reader)
    components = reader.add(container.library, 'Components')
    for _ in range(container.header.entry_count):
        read_component(reader, components)
    if reader.pos != len(reader.data):
        raise reader.error_type(f'unconsumed library data at byte {reader.pos:#x}')
    return DecodedLibrary(container.header, container.library)
