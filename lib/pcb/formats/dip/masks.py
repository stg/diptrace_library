"""Mask overrides and same-net rules added after the initial PCB records."""
from ....common.footprint_codec import read_pad_mask_states
from .preamble import _fields


def _extend_drc(reader, drc):
    _fields(reader, drc, 'boolean', 'CheckKeepouts CheckSameNet CheckSameComponentPads')
    for layer in drc.select('LayClearances/LayClearance'):
        _fields(reader, layer, 'number', 'SameTraceToTrace SameSmdToVia SameSmdToPad SameSmdToSmd')


def read_mask_extensions(reader, board, cached_definitions):
    if reader.header.version <= 44:
        return
    _fields(reader, board.one('Settings'), 'number', 'SolderMaskSwell PasteMaskShrink')
    _extend_drc(reader, board.one('DRC'))
    _extend_drc(reader, board.one('LastDRC'))
    for component in board.select('Components/Component'):
        for pad in component.select('Pattern/Pads/Pad'):
            read_pad_mask_states(reader, pad, extended=True)
    for cached in cached_definitions:
        for pad in cached.definition.select('Pattern/Pads/Pad'):
            read_pad_mask_states(reader, pad, extended=True)
