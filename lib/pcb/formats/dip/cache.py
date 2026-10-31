"""Embedded library definitions with PCB geometry and revision policy."""
from decimal import Decimal
import math

from ....common.model import SourceSpan
from ....common.library_codec import LibraryCodecs, read_library_cache
from ....common.footprint_codec import (read_parameters, read_pad_geometry,
                                       read_pad_mask_states, read_model)
from ....common.symbol_codec import read_cached_drawings
from .components import _graphics


def _pads(reader, pattern):
    pads = pattern.add('Pads')
    count = pattern.annotations['declared_pad_count']
    for index in range(count):
        start = reader.pos
        inverted = reader.boolean()
        number = reader.argument('integer')
        x, y = reader.argument('number'), reader.argument('number')
        label, name = reader.argument('text'), reader.argument('text')
        pad = pads.add('Pad', index, label, name, x, y)
        pad.add('Number_New', number)
        pad.add('PadAngle', Decimal(str(math.pi/2)) if inverted else Decimal(0))
        if index in (0, count-1):
            pad.annotations['reserved'] = True
        read_pad_geometry(reader, pad)
        reader.field(pad, 'Locked', 'boolean')
        reader.field(pad, 'Sided', 'boolean')
        read_pad_mask_states(reader, pad)
        reader.fields(pad, (('CustomSwell_New', 'number'), ('CustomShrink_New', 'number')))
        pad.source = SourceSpan('dip', start, reader.pos, reader.source)
    return pads


def _pattern_graphics(reader, pattern):
    return _graphics(reader, pattern, text_markers=False)


def _symbol_graphics(reader, part):
    return read_cached_drawings(reader, part, physical_points=reader.header.version >= 47)


_CODECS = LibraryCodecs(read_parameters, _pads, _pattern_graphics, read_model, _symbol_graphics,
                        definition_text='Datasheet')


def read_cache(reader, board):
    if reader.header.version <= 38:
        board.add('DesignCache_Count', -1)
        board.add('DesignCache_Links')
        return ()
    return read_library_cache(reader, board, _CODECS)
