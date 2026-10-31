"""Authored pad pairs and group policy; supplied ratlines are calculated data."""
from ..errors import PcbError


def _pad(key, positions, path):
    if key not in positions:
        raise PcbError(f'{path}: unresolved internal connection pad {key}')
    return positions[key]


def _integer_content(record):
    value = record.content()
    if value.kind != 'number' or value.unit or value.value != int(value.value):
        raise PcbError(f'{record.node.path}: expected an integer pad identity')
    record.finish(allow_text=True)
    return int(value.value)


def read_connections(record, component, *, pad_positions):
    pairs = component.add('InternalConnection_Records')
    for item in record.rows('IntConRecords', 'Item'):
        pairs.add('pt', *(_pad(item.integer(axis), pad_positions, item.node.path) for axis in ('X', 'Y')))
        item.finish()
    groups = component.add('InternalConnections')
    for index, source in enumerate(record.rows('InternalConnections', 'IntCon')):
        group = groups.add('IntCon', index)
        group.add('ConnectAll', source.boolean('ConnectAll', False))
        pads = group.add('PadId')
        for item in source.rows('PadId', 'Item'):
            pads.add('Item', _pad(_integer_content(item), pad_positions, item.node.path))
        # These endpoints display an existing group's connectivity. Shared model
        # assembly derives the display tree from current member identities and
        # pad coordinates; retaining an old edge list would duplicate that fact.
        for line in source.rows('Ratlines', 'Ratline'):
            line.integer('X')
            line.integer('Y')
            line.finish()
        source.finish()
