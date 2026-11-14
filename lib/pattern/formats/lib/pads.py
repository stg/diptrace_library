"""Standalone pad rows, with revision policy around shared physical facts."""
import math

from ....common.footprint_codec import read_pad_mask_states, read_pad_extensions
from .parameters import _fields


def read_pads(reader, pattern):
    version = reader.header.version
    pads = reader.add(pattern, 'Pads')
    for index in range(reader.count('pattern pads')):
        pad = reader.add(pads, 'Pad', index)
        reader.field_into(pad, 'Number_New', 'integer')
        _fields(reader, pad, 'number', 'X Y')
        if version < 20:
            reader.add_into(pad, 'PadAngle', math.pi/2 if reader.boolean() else 0)
        _fields(reader, pad, 'text', 'StringNumber Name')
        _fields(reader, pad, 'number', 'PadWidth_New PadHeight_New PadHole PadHoleH')
        reader.field_into(pad, 'PadHoleType', 'integer')
        reader.field_into(pad, 'SurfacePad', 'boolean')
        reader.field_into(pad, 'PadShape_New', 'integer')
        reader.field_into(pad, 'Standard', 'boolean')
        contour = reader.add(pad, 'PadPoints_New')
        reader.points(contour, reader.count('pad contour points'))
        _fields(reader, pad, 'boolean', 'Locked Sided')
        read_pad_mask_states(reader, pad, extended=version >= 19)
        _fields(reader, pad, 'number', 'CustomSwell_New CustomShrink_New')
        if version >= 20:
            reader.field_into(pad, 'Group', 'integer')
            read_pad_extensions(reader, pad)
    return pads
