"""DCH library records with schematic geometry-version policy."""
from ....common.library_codec import LibraryCodecs, read_library_cache
from ....common.symbol_codec import read_cached_drawings
from .read import _pattern_graphics, _pattern_model, _pattern_pads, _pattern_parameters


def _pads(reader, pattern):
    _pattern_pads(reader, pattern, omit_reserved=False)


def _symbol_graphics(reader, part):
    return read_cached_drawings(reader, part, physical_points=reader.header.version >= 40)


_CODECS = LibraryCodecs(_pattern_parameters, _pads, _pattern_graphics, _pattern_model,
                        _symbol_graphics, definition_text='ModelNote')


def read_cache(reader, schematic):
    return read_library_cache(reader, schematic, _CODECS)
