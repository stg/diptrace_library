"""Append-only current schematic fields, using public format vocabulary."""
from ...model.traversal import (footprints)


def read_recent_extensions(r, schematic):
    # Older inputs use the net's saved array position as its default identity.
    for index, net in enumerate(schematic.child('Nets').children('Net')):
        if r.header.version >= 47:
            r.field_into(net, 'HiddenId', 'integer')
        else:
            r.add_into(net, 'HiddenId', index)
    # This is a FOOTPRINT drawing attribute, not a symbol pin field.
    for pattern in footprints(schematic):
        for shape in pattern.child('Shapes').children('Shape'):
            if r.header.version >= 48:
                r.field_into(shape, 'PadId', 'integer')
            else:
                r.add_into(shape, 'PadId', -1)
    from .versions import (read_extensions)
    read_extensions(r, schematic)
