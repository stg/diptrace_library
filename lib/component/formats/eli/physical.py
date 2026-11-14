"""Attached footprint parameters in a standalone component part.

Standalone authoring properties precede pad rows here; cached definitions place
them in a later extension. The named physical facts use the same shared codecs.
"""
import math

from ....common.footprint_codec import (read_parameters, read_pattern_authoring,
    read_pad_geometry, read_pad_mask_states, read_pad_extensions)
from ....common.footprint_records import PATTERN


def read_physical_parameters(reader, owner, part):
    """Consume the parameter block, leaving the cursor before the pad count."""
    pattern = reader.add(owner, 'Pattern')
    connections = reader.add(pattern, 'InternalConnections')
    for _ in range(reader.count('internal pad connections')):
        reader.record(connections, 'IntCon', 'integer', 'integer')
    read_parameters(reader, pattern)
    reader.fields(part, ((name, 'number') for name in ('Origin_X', 'Origin_Y')))
    points = reader.add(pattern, 'PadPoints')
    reader.points(points, reader.count('default pad points'))
    if reader.header.version >= 27:
        read_pattern_authoring(reader, pattern)
    return pattern.bind_schema(PATTERN)


def read_pads(reader, pattern):
    """Read local pad slots; the import model later removes boundary records."""
    version = reader.header.version
    pads = reader.add(pattern, 'Pads')
    for index in range(reader.count('attached footprint pads')):
        pad = reader.add(pads, 'Pad', index)
        if version < 27:
            reader.add_into(pad, 'PadAngle', math.pi/2 if reader.boolean() else 0)
        reader.field_into(pad, 'Number_New', 'integer')
        reader.fields(pad, ((name, 'number') for name in ('X', 'Y')))
        reader.fields(pad, ((name, 'text') for name in ('StringNumber', 'Name')))
        read_pad_geometry(reader, pad)
        reader.fields(pad, ((name, 'boolean') for name in ('Locked', 'Sided')))
        read_pad_mask_states(reader, pad, extended=version >= 26)
        reader.fields(pad, ((name, 'number') for name in ('CustomSwell_New', 'CustomShrink_New')))
        if version >= 27:
            reader.field_into(pad, 'Group', 'integer')
            read_pad_extensions(reader, pad)
    return pads
