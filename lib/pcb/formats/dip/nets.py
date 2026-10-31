"""Initial connection and routing records, before revision extensions.

The returned upgrade inputs are consumed while loading the complete document.
They are not additional authored properties of the current PCB model.
"""
from ....common.model import SourceSpan
from ..assembly.routing_inputs import NetInput, TraceInput
from .preamble import _fields


def read_connections(reader, board):
    connections = board.add('Connections')
    for index in range(reader.count('connections')):
        start = reader.pos
        connection = connections.add('Connection', index)
        reader.field(connection, 'Enabled', 'boolean')
        _fields(reader, connection, 'number', 'X1 Y1 X2 Y2')
        _fields(reader, connection, 'integer', 'Comp1 Comp2 Pad1 Pad2')
        if reader.header.version > 33:
            reader.field(connection, 'Hidden', 'boolean')
        else:
            connection.add('Hidden', False)
        connection.source = SourceSpan('dip', start, reader.pos, reader.source)
    return connections


def _points(reader, trace, *, necked=False):
    points = trace.add('Points')
    for index in range(reader.count('trace points')):
        start = reader.pos
        point = points.add('Point', index)
        _fields(reader, point, 'number', 'X Y')
        reader.field(point, 'Lay', 'integer')
        reader.integer()  # Reconstructable direction classification of the incoming segment.
        reader.field(point, 'Width', 'number')
        reader.number()  # Via geometry is resolved from the current style identity.
        reader.boolean()
        reader.field(point, 'Jumper', 'integer')
        reader.field(point, 'Arc', 'boolean')
        reader.field(point, 'ViaStyle', 'integer')
        reader.number()
        reader.integer()
        reader.integer()
        reader.field(point, 'Selected', 'boolean')
        if necked:
            reader.field(point, 'PairNecked', 'boolean')
        point.source = SourceSpan('dip', start, reader.pos, reader.source)
    return tuple(points.children())


def _traces(reader, net):
    traces = net.add('Traces')
    upgrades = []
    for index in range(reader.count('traces')):
        start = reader.pos
        trace = traces.add('Trace', index)
        _fields(reader, trace, 'integer', 'Object1 SubObject1 Point1 Object2 SubObject2 Point2')
        linked = (reader.boolean(), reader.boolean())
        free = (reader.boolean(), reader.boolean())
        for end in range(2):
            # A free end takes precedence over the older trace-link indicator.
            trace.add('Connected'+str(end+1), -1 if free[end] else int(linked[end]))
        reader.field(trace, 'Selected', 'boolean')
        reader.field(trace, 'Group', 'integer')
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
    nets = board.add('Nets')
    upgrades = []
    for _ in range(reader.count('nets')):
        start = reader.pos
        net = nets.add('Net')
        reader.field(net, 'Enabled', 'boolean')
        reader.boolean()  # Obsolete net selection slot.
        _fields(reader, net, 'integer', 'ActivePoint ActiveLine')
        reader.integer()  # Obsolete grouping slot.
        _fields(reader, net, 'integer', 'Number RouteMode')
        _fields(reader, net, 'number', 'Width Clearance')
        reader.field(net, 'Name', 'text')
        # Repeated compatibility dimensions of the default via style. The
        # current design owns these through its via-style table, not per net.
        reader.number()
        reader.number()
        reader.boolean()
        _fields(reader, net, 'boolean', 'HideRatlines Locked ShowLength CustomColor')
        reader.field(net, 'TraceColor', 'color')
        reader.field(net, 'NetClass', 'integer')
        pads = net.add('Pads')
        for _ in range(reader.count('net pads')):
            reader.record(pads, 'Item', 'integer', 'integer')
        traces = _traces(reader, net)
        net.source = SourceSpan('dip', start, reader.pos, reader.source)
        upgrades.append(NetInput(net, traces))
    return tuple(upgrades)
