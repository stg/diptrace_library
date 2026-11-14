"""Standalone component footprint graphics with family-owned revision gates."""
from ....common.library_graphics import read_library_graphics


def read_physical_graphics(reader, pattern):
    version = reader.header.version
    return read_library_graphics(reader, pattern, physical_coordinates=version >= 27,
        drawing_pad_links=version >= 32, extended_fonts=version >= 33)
