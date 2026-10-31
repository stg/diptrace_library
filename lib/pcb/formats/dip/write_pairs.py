"""Differential routing sections generated from supplied geometry and references.

These writers preserve authored and calculated routing data. They do not route
connections, tune lengths or calculate phase measurements.
"""
from ....common.conversion import warn
from ...model import routing_records as model
from ...model.pair_ranges import missing_name
from ..errors import PcbError
from ..output_indices import OutputIndices, ordered_layer_rows, pad_number
from ..output_validation import check_tree, field_value
from ..routing_projection import center_directions
from .write_nets import write_trace, write_point_pair_extensions, write_trace_relationships
from .write_results import write_result_qualifications
from .write_settings import write_drc


def _pairs(board):
    if (source := board.child('DifferentialPairs')) is not None:
        check_tree(source, model.COLLECTIONS['DifferentialPairs'], destination='DIP')
    return board.select('DifferentialPairs/DifferentialPair')


def _removed_pairs(board):
    if (source := board.child('RemovedDifferentialPairs')) is not None:
        check_tree(source, model.COLLECTIONS['RemovedDifferentialPairs'], destination='DIP')
    return board.select('RemovedDifferentialPairs/RemovedDifferentialPair')


def _side_points(center):
    for side in ('Pos', 'Neg'):
        yield from center.select(side+'Points/'+side+'Point')


def _pair(writer, pair, indices):
    if pair['PosNet'] is None or pair['NegNet'] is None:
        raise PcbError(f'{pair.path}: differential-pair output needs both current nets')
    writer.field(pair, 'Enabled', 'boolean')
    writer.field(pair, 'Name', 'text')
    writer.integer(pair['Id'])
    writer.fields(pair, 'integer', 'PosNetIndex NegNetIndex')
    writer.integer(indices.class_number(pair['Class']))
    writer.field(pair, 'CustomColor', 'boolean')
    writer.field(pair, 'TraceColor', 'color')
    pads = pair.select('PadPoints/PadPoint')
    writer.integer(len(pads))
    for row in pads:
        for side in ('Pos', 'Neg'):
            writer.field(row, side+'ComponentIndex', 'integer')
            writer.integer(pad_number(row[side+'Pad']))
    segments = pair.select('Segments/Segment')
    writer.integer(len(segments))
    for segment in segments:
        writer.fields(segment, 'integer', 'PosTraceIndex NegTraceIndex StartPoint EndPoint StartSegment EndSegment')
        centers = segment.select('CenterPoints/CenterPoint')
        writer.integer(len(centers))
        for center, direction in zip(centers, center_directions(centers)):
            writer.fields(center, 'number', 'X Y')
            writer.fields(center, 'integer', 'Lay ViaStyle')
            writer.integer(direction)
            writer.field(center, 'Type', 'integer')
            for side in ('Pos', 'Neg'):
                for end in ('Start', 'End'):
                    writer.field(center, side+'Trace_'+end+'Point', 'integer')
            if any(center.child(missing_name(side, end)) is not None
                   for side in ('Pos', 'Neg') for end in ('Start', 'End')):
                warn(writer.report, 'unresolved-pair-range', 'dip',
                     'Retained a differential center range whose point cannot be resolved', (center,),
                     recoverability='current range index and trace scope retained')
            writer.field(center, 'PosTraceSide', 'integer')
            writer.fields(center, 'boolean', 'Necked Selected PhaseError')
            for side in ('Pos', 'Neg'):
                points = center.select(side+'Points/'+side+'Point')
                writer.integer(len(points))
                for point in points:
                    writer.fields(point, 'number', 'X Y')
                    writer.field(point, 'Selected', 'boolean')


def write_initial_pairs(writer, board, *, indices=None):
    """Pair bodies, class neck/phase settings, point phases and check selectors."""
    indices = indices or OutputIndices(board)
    pairs = _pairs(board)
    layers = board.select('Layers/Layer')
    for net_class in indices.classes:
        writer.fields(net_class, 'number', 'Phase Phase_ErrorLength')
        rows = ordered_layer_rows(net_class.select('LayProperties/LayProperty'), layers,
                                  uniform=field_value(net_class, 'AllLayers'), path=net_class.path)
        for row in rows:
            writer.fields(row, 'number', 'Neck_Width Neck_DifClearance Neck_MaxLength')
    writer.integer(len(pairs))
    for pair in pairs:
        _pair(writer, pair, indices)
    write_point_pair_extensions(writer, board)
    write_result_qualifications(writer, board, indices=indices)
    removed = _removed_pairs(board)
    writer.integer(len(removed))
    for pair in removed:
        _pair(writer, pair, indices)


def write_routing_extensions(writer, board):
    """Last-used rules, pair side layers, separate routes and endpoint modes."""
    pairs = _pairs(board)
    write_drc(writer, board, 'LastDRC')
    for pair in pairs:
        writer.field(pair, 'AutoPadPoints', 'boolean')
        writer.field(pair, 'RouteMode', 'integer')
        for center in pair.select('Segments/Segment/CenterPoints/CenterPoint'):
            for point in _side_points(center):
                writer.fields(point, 'integer', 'Lay ViaStyle')
                writer.field(point, 'Necked', 'boolean')
        for side in ('Pos', 'Neg'):
            traces = pair.select(side+'SeparateTraces/'+side+'Trace')
            writer.integer(len(traces))
            for trace in traces:
                write_trace(writer, trace, separate=True)
    write_trace_relationships(writer, board)
    for pair in _removed_pairs(board):
        for center in pair.select('Segments/Segment/CenterPoints/CenterPoint'):
            for point in _side_points(center):
                writer.fields(point, 'integer', 'Lay ViaStyle')
                writer.field(point, 'Necked', 'boolean')


def _side_meanders(writer, pair):
    for center in pair.select('Segments/Segment/CenterPoints/CenterPoint'):
        for point in _side_points(center):
            writer.field(point, 'Meander', 'integer')
            writer.field(point, 'MeanderAngle', 'number')
            writer.field(point, 'Arc', 'boolean')


def write_meanders(writer, board):
    """Stored tuning/arc data, without calculating or changing any geometry."""
    for net in board.select('Nets/Net'):
        writer.field(net, 'MeanderGap', 'number')
        for point in net.select('Traces/Trace/Points/Point'):
            writer.field(point, 'Meander', 'integer')
            writer.field(point, 'MeanderAngle', 'number')
    for pair in _pairs(board):
        _side_meanders(writer, pair)
        for side in ('Pos', 'Neg'):
            for point in pair.select(side+'SeparateTraces/'+side+'Trace/Points/Point'):
                writer.field(point, 'Meander', 'integer')
                writer.field(point, 'MeanderAngle', 'number')
    for pair in _removed_pairs(board):
        _side_meanders(writer, pair)
