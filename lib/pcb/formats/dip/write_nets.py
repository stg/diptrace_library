"""Binary net, guide and trace sections generated from current relationships.

The initial routing section precedes differential routing and the authoritative
endpoint modes. These functions are composed in stream order by the adapter;
none produces a complete file on its own.
"""
from ...model import definitions, routing_records, ratlines
from ..connection_types import CONNECTION_CODES
from ..output_indices import OutputIndices, pad_number
from ..output_validation import check_tree, field_value
from ..routing_projection import point_directions, point_memberships, peer_backlink, via_geometry
from ..routing_values import BINARY_UNAVAILABLE_PHASE


def write_connections(writer, board):
    source = board.child('Ratlines')
    if source is not None:
        check_tree(source, ratlines.RATLINES, destination='DIP')
    rows = board.select('Ratlines/Ratline')
    writer.integer(len(rows))
    for row in rows:
        writer.field(row, 'Enabled', 'boolean')
        writer.fields(row, 'number', 'X1 Y1 X2 Y2')
        writer.fields(row, 'integer', 'ComponentIndex1 ComponentIndex2')
        writer.integer(pad_number(row['Pad1']))
        writer.integer(pad_number(row['Pad2']))
        writer.field(row, 'Hidden', 'boolean')


def write_trace_points(writer, trace, *, separate=False):
    points = trace.select('Points/Point')
    writer.integer(len(points))
    for point, direction in zip(points, point_directions(points)):
        geometry = via_geometry(point['Via'])
        writer.fields(point, 'number', 'X Y')
        writer.field(point, 'Lay', 'integer')
        writer.integer(direction)
        writer.field(point, 'Width', 'number')
        writer.number(geometry['ViaSize'])
        writer.boolean(geometry['ThroughVia'])
        writer.field(point, 'Jumper', 'integer')
        writer.field(point, 'Arc', 'boolean')
        writer.field(point, 'ViaStyle', 'integer')
        writer.number(geometry['ViaHole'])
        writer.integer(geometry['ViaFrom'])
        writer.integer(geometry['ViaTo'])
        writer.field(point, 'Selected', 'boolean')
        if separate:
            writer.field(point, 'PairNecked', 'boolean')


def write_trace(writer, trace, *, separate=False):
    check_tree(trace, routing_records.SEPARATE_TRACE if separate else routing_records.TRACE,
               destination='DIP')
    writer.fields(trace, 'integer', 'Object1 SubObject1 Point1 Object2 SubObject2 Point2')
    if separate:
        for end in (1, 2):
            writer.integer(CONNECTION_CODES[trace['Connected'+str(end)]])
    else:
        for kind in ('Trace', 'Free'):
            for end in (1, 2):
                writer.boolean(trace['Connected'+str(end)] == kind)
    writer.field(trace, 'Selected', 'boolean')
    writer.field(trace, 'Group', 'integer')
    if separate:
        writer.field(trace, 'TraceId', 'integer')
    writer.field(trace, 'Id', 'integer')
    write_trace_points(writer, trace, separate=separate)


def write_base_nets(writer, board, *, indices=None):
    indices = indices or OutputIndices(board)
    source = board.one('Nets')
    check_tree(source, definitions.COLLECTIONS['Nets'], destination='DIP')
    nets = source.children('Net')
    styles = board.select('ViaStyles/ViaStyle')
    compatibility = via_geometry(styles[0] if styles else None)
    writer.integer(len(nets))
    for net in nets:
        writer.field(net, 'Enabled', 'boolean')
        writer.boolean(False)
        writer.fields(net, 'integer', 'ActivePoint ActiveLine')
        writer.integer(-1)
        writer.fields(net, 'integer', 'Number RouteMode')
        writer.fields(net, 'number', 'Width Clearance')
        writer.field(net, 'Name', 'text')
        writer.number(compatibility['ViaSize'])
        writer.number(compatibility['ViaRing'])
        writer.boolean(compatibility['ThroughVia'])
        writer.fields(net, 'boolean', 'HideRatlines Locked ShowLength CustomColor')
        writer.field(net, 'TraceColor', 'color')
        writer.integer(indices.class_number(net['Class']))
        members = net.select('Pads/Item')
        writer.integer(len(members))
        for member in members:
            writer.field(member, 'ComponentIndex', 'integer')
            writer.integer(pad_number(member['Pad']))
        traces = net.select('Traces/Trace')
        writer.integer(len(traces))
        for trace in traces:
            write_trace(writer, trace)


def write_point_pair_extensions(writer, board):
    """Current pair membership and calculated phase, after pair geometry."""
    for trace in board.select('Nets/Net/Traces/Trace'):
        for point, (center, _) in zip(trace.select('Points/Point'), point_memberships(trace)):
            writer.integer(center)
            for name in ('PhaseFwd', 'PhaseBack'):
                value = field_value(point, name)
                writer.number(BINARY_UNAVAILABLE_PHASE if value is None else value)


def write_trace_relationships(writer, board):
    """Authoritative endpoint modes and pair-run selectors supersede old flags."""
    for trace in board.select('Nets/Net/Traces/Trace'):
        writer.integer(peer_backlink(trace))
        for end in (1, 2):
            writer.integer(CONNECTION_CODES[trace['Connected'+str(end)]])
        for point, (_, subpoint) in zip(trace.select('Points/Point'), point_memberships(trace)):
            writer.integer(subpoint)
            writer.field(point, 'PairNecked', 'boolean')
