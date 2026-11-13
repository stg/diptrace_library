"""Embedded library definitions with PCB geometry and revision policy."""
from decimal import Decimal
import math

from ....common.model import SourceSpan
from ....common.library_codec import LibraryCodecs, read_library_cache
from ....common.footprint_codec import (read_parameters, read_pad_geometry,
                                       read_pad_mask_states, read_model)
from ....common.symbol_codec import read_cached_drawings
from .components import _graphics


def _pads(reader, pattern, *, count):
    pads = reader.add(pattern, 'Pads')
    for index in range(count):
        start = reader.pos
        inverted = reader.boolean()
        number = reader.argument('integer')
        x, y = reader.argument('number'), reader.argument('number')
        label, name = reader.argument('text'), reader.argument('text')
        pad = reader.add(pads, 'Pad', index, label, name, x, y)
        reader.add_into(pad, 'Number_New', number)
        reader.add_into(pad, 'PadAngle', Decimal(str(math.pi/2)) if inverted else Decimal(0))
        read_pad_geometry(reader, pad)
        reader.field_into(pad, 'Locked', 'boolean')
        reader.field_into(pad, 'Sided', 'boolean')
        read_pad_mask_states(reader, pad)
        reader.fields(pad, (('CustomSwell_New', 'number'), ('CustomShrink_New', 'number')))
        pad.source = SourceSpan('dip', start, reader.pos, reader.source)
    return pads


def _pattern_graphics(reader, pattern):
    return _graphics(reader, pattern, text_markers=False)


def _symbol_graphics(reader, part, *, count):
    return read_cached_drawings(reader, part, count=count, physical_points=reader.header.version >= 47)


_CODECS = LibraryCodecs(read_parameters, _pads, _pattern_graphics, read_model, _symbol_graphics,
                        definition_text='Datasheet')


def read_cache(reader, board):
    if reader.header.version <= 38:
        reader.add_into(board, 'DesignCache_Count', -1)
        reader.add_into(board, 'DesignCache_Links')
        return ()
    return read_library_cache(reader, board, _CODECS)
