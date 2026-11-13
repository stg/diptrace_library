"""Initial connection and routing records, before revision extensions.

The returned upgrade inputs are consumed while loading the complete document.
They are not additional authored properties of the current PCB model.
"""
from ....common.model import SourceSpan
from ..assembly.routing_inputs import NetInput, TraceInput
from .preamble import _fields


def read_connections(reader, board):
    connections = reader.add(board, 'Connections')
    for index in range(reader.count('connections')):
        start = reader.pos
        connection = reader.add(connections, 'Connection', index)
        reader.field_into(connection, 'Enabled', 'boolean')
        _fields(reader, connection, 'number', 'X1 Y1 X2 Y2')
        _fields(reader, connection, 'integer', 'Comp1 Comp2 Pad1 Pad2')
        if reader.header.version > 33:
            reader.field_into(connection, 'Hidden', 'boolean')
        else:
            reader.add_into(connection, 'Hidden', False)
        connection.source = SourceSpan('dip', start, reader.pos, reader.source)
    return connections


def _points(reader, trace, *, necked=False):
    points = reader.add(trace, 'Points')
    for index in range(reader.count('trace points')):
        start = reader.pos
        point = reader.add(points, 'Point', index)
        _fields(reader, point, 'number', 'X Y')
        reader.field_into(point, 'Lay', 'integer')
        reader.integer()  # Reconstructable direction classification of the incoming segment.
        reader.field_into(point, 'Width', 'number')
        reader.number()  # Via geometry is resolved from the current style identity.
        reader.boolean()
        reader.field_into(point, 'Jumper', 'integer')
        reader.field_into(point, 'Arc', 'boolean')
        reader.field_into(point, 'ViaStyle', 'integer')
        reader.number()
        reader.integer()
        reader.integer()
        reader.field_into(point, 'Selected', 'boolean')
        if necked:
            reader.field_into(point, 'PairNecked', 'boolean')
        point.source = SourceSpan('dip', start, reader.pos, reader.source)
    return tuple(points.children())


def _traces(reader, net):
    traces = reader.add(net, 'Traces')
    upgrades = []
    for index in range(reader.count('traces')):
        start = reader.pos
        trace = reader.add(traces, 'Trace', index)
        _fields(reader, trace, 'integer', 'Object1 SubObject1 Point1 Object2 SubObject2 Point2')
        linked = (reader.boolean(), reader.boolean())
        free = (reader.boolean(), reader.boolean())
        for end in range(2):
            # A free end takes precedence over the older trace-link indicator.
            reader.add_into(trace, 'Connected'+str(end+1), -1 if free[end] else int(linked[end]))
        reader.field_into(trace, 'Selected', 'boolean')
        reader.field_into(trace, 'Group', 'integer')
        previous_number = reader.integer()
        points = _points(reader, trace)
        trace.source = SourceSpan('dip', start, reader.pos, reader.source)
        upgrades.append(TraceInput(trace, previous_number, points))
    return tuple(upgrades)


def read_base_nets(reader, board):
    """Read net membership and trace geometry for supported PCB revisions.

    Later sections supply current via settings, identities, differential-pair
    relationships and other properties. Binding and modernization follow those
    sections, rather than exposing this intermediate tree as a document.
    """
    nets = reader.add(board, 'Nets')
    upgrades = []
    for _ in range(reader.count('nets')):
        start = reader.pos
        net = reader.add(nets, 'Net')
        reader.field_into(net, 'Enabled', 'boolean')
        reader.boolean()  # Obsolete net selection slot.
        _fields(reader, net, 'integer', 'ActivePoint ActiveLine')
        reader.integer()  # Obsolete grouping slot.
        _fields(reader, net, 'integer', 'Number RouteMode')
        _fields(reader, net, 'number', 'Width Clearance')
        reader.field_into(net, 'Name', 'text')
        # Repeated compatibility dimensions of the default via style. The
        # current design owns these through its via-style table, not per net.
        reader.number()
        reader.number()
        reader.boolean()
        _fields(reader, net, 'boolean', 'HideRatlines Locked ShowLength CustomColor')
        reader.field_into(net, 'TraceColor', 'color')
        reader.field_into(net, 'NetClass', 'integer')
        pads = reader.add(net, 'Pads')
        for _ in range(reader.count('net pads')):
            reader.record(pads, 'Item', 'integer', 'integer')
        traces = _traces(reader, net)
        net.source = SourceSpan('dip', start, reader.pos, reader.source)
        upgrades.append(NetInput(net, traces))
    return tuple(upgrades)
