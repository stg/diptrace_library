"""DCH library records with schematic geometry-version policy."""
from ....common.library_codec import LibraryCodecs, read_library_cache
from ....common.conversion import import_notice
from ....common.symbol_codec import read_cached_drawings
from .binary import DchError
from .read import _pattern_graphics, _pattern_model, _pattern_pads, _pattern_parameters


def _pads(reader, pattern):
    _pattern_pads(reader, pattern, omit_reserved=False)


def _symbol_graphics(reader, part):
    return read_cached_drawings(reader, part, physical_points=reader.header.version >= 40)


_CODECS = LibraryCodecs(_pattern_parameters, _pads, _pattern_graphics, _pattern_model,
                        _symbol_graphics, definition_text='ModelNote')


def read_cache(reader, schematic):
    inputs = read_library_cache(reader, schematic, _CODECS)
    unused = []
    for slot in schematic.select('CacheLib/Slots/Slot'):
        if slot.children('Definition'):
            continue
        if reader.header.version >= 45:
            raise DchError(f'{slot.path}: DCH schema {reader.header.version} '
                           'requires at least one definition per library slot')
        # Earlier slots can be empty, but their trailing path has no definition
        # to own it. Consume the field without making it an authored reference.
        if slot.values[1]:
            slot.set_values(slot.values[0], '')
            unused.append(slot)
    if unused:
        import_notice('info', 'unused-library-path',
                      'Cleared unused paths on empty library slots.', unused,
                      recoverability='the empty slots remain; no definition owns these paths')
    return inputs
