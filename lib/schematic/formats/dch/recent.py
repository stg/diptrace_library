"""Append-only current schematic fields, using public format vocabulary."""
from ...model.traversal import (footprints)


def read_recent_extensions(r, schematic):
    # Older inputs use the net's saved array position as its default identity.
    for index, net in enumerate(schematic.child('Nets').children('Net')):
        if r.header.version >= 47:
            node = r.field(net, 'HiddenId', 'integer')
        else:
            node = net.add('HiddenId', index)
            node.annotations['default_for_version'] = r.header.version
        node.annotations['asc_omit'] = 'net HiddenId is emitted by XML, not the inspected ASC exporters'
    # This is a FOOTPRINT drawing attribute, not a symbol pin field.
    for pattern in footprints(schematic):
        for shape in pattern.child('Shapes').children('Shape'):
            if r.header.version >= 48:
                node = r.field(shape, 'PadId', 'integer')
            else:
                node = shape.add('PadId', -1)
                node.annotations['default_for_version'] = r.header.version
            node.annotations['asc_omit'] = 'drawing PadId is emitted by XML, not the inspected ASC exporters'
    from .versions import (read_extensions)
    read_extensions(r, schematic)
