"""Initial differential-pair geometry and its routing relationships."""
from ....common.model import SourceSpan
from ..assembly.routing_inputs import TraceInput
from .nets import _points
from .preamble import _fields
from .settings import read_drc


def _side_points(reader, center, collection, kind):
    points = reader.add(center, collection)
    for index in range(reader.count('differential '+collection)):
        point = reader.add(points, kind, index)
        _fields(reader, point, 'number', 'X Y')
        reader.field_into(point, 'Selected', 'boolean')
    return points


def _pair(reader, pairs, index, kind='DifferentialPair'):
    start = reader.pos
    pair = reader.add(pairs, kind, index)
    reader.field_into(pair, 'Enabled', 'boolean')
    reader.field_into(pair, 'Name', 'text')
    _fields(reader, pair, 'integer', 'Number PosNet NegNet NetClass')
    reader.field_into(pair, 'CustomColor', 'boolean')
    reader.field_into(pair, 'TraceColor', 'color')
    pads = reader.add(pair, 'PadPoints')
    for pad_index in range(reader.count('paired pads')):
        pad = reader.add(pads, 'PadPoint', pad_index)
        _fields(reader, pad, 'integer', 'PosComp PosPad NegComp NegPad')
    segments = reader.add(pair, 'Segments')
    for segment_index in range(reader.count('paired segments')):
        segment = reader.add(segments, 'Segment', segment_index)
        _fields(reader, segment, 'integer', 'PosTrace NegTrace StartPoint EndPoint StartSegment EndSegment')
        centers = reader.add(segment, 'CenterPoints')
        for center_index in range(reader.count('paired center points')):
            center = reader.add(centers, 'CenterPoint', center_index)
            _fields(reader, center, 'number', 'X Y')
            _fields(reader, center, 'integer',
                    'Lay ViaStyle Orientation Type PosTrace_StartPoint PosTrace_EndPoint '
                    'NegTrace_StartPoint NegTrace_EndPoint PosTraceSide')
            _fields(reader, center, 'boolean', 'Necked Selected PhaseError')
            _side_points(reader, center, 'PosPoints', 'PosPoint')
            _side_points(reader, center, 'NegPoints', 'NegPoint')
    pair.source = SourceSpan('dip', start, reader.pos, reader.source)
    return pair


def read_initial_pairs(reader, board):
    """Read the schema-40 additions; later revisions extend these same records."""
    if reader.header.version <= 39:
        # Earlier revisions load ordinary point phase lengths as zero, even
        # though they have no differential-routing section to store them.
        for point in board.select('Nets/Net/Traces/Trace/Points/Point'):
            reader.add_into(point, 'PhaseFwd', 0)
            reader.add_into(point, 'PhaseBack', 0)
        return None
    for net_class in board.select('NetClasses/NetClass'):
        _fields(reader, net_class, 'number', 'Phase Phase_ErrorLength')
        for layer in net_class.select('LayProperties/LayProperty'):
            _fields(reader, layer, 'number', 'Neck_Width Neck_DifClearance Neck_MaxLength')
    pairs = reader.add(board, 'DifferentialPairs')
    for index in range(reader.count('differential pairs')):
        _pair(reader, pairs, index)
    for point in board.select('Nets/Net/Traces/Trace/Points/Point'):
        reader.field_into(point, 'PairPoint', 'integer')
        _fields(reader, point, 'number', 'PhaseFwd PhaseBack')
    for error in board.select('DesignErrors/DesignError'):
        _fields(reader, error, 'integer', 'RuleType RuleLay ObjectNetClass1 ObjectNetClass2')
    removed = reader.add(board, 'RemovedDifferentialPairs')
    # The first revision with differential routing also accepts an early file
    # ending before the removed-pair list was added.
    if reader.pos < len(reader.data):
        for index in range(reader.count('removed differential pairs')):
            _pair(reader, removed, index, 'RemovedDifferentialPair')
    return pairs


def _extend_side_points(reader, pair):
    for segment in pair.select('Segments/Segment'):
        for center in segment.select('CenterPoints/CenterPoint'):
            for collection, kind in (('PosPoints', 'PosPoint'), ('NegPoints', 'NegPoint')):
                for point in center.select(collection+'/'+kind):
                    _fields(reader, point, 'integer', 'Lay ViaStyle')
                    reader.field_into(point, 'Necked', 'boolean')


def _separate_traces(reader, pair, side):
    traces = reader.add(pair, side+'SeparateTraces')
    upgrades = []
    for index in range(reader.count(side.lower()+' separate traces')):
        start = reader.pos
        trace = reader.add(traces, side+'Trace', index)
        _fields(reader, trace, 'integer', 'Object1 SubObject1 Point1 Object2 SubObject2 Point2 Connected1 Connected2')
        reader.field_into(trace, 'Selected', 'boolean')
        _fields(reader, trace, 'integer', 'Group TraceId')
        previous_number = reader.integer()
        points = _points(reader, trace, necked=True)
        trace.source = SourceSpan('dip', start, reader.pos, reader.source)
        upgrades.append(TraceInput(trace, previous_number, points))
    return tuple(upgrades)


def read_routing_extensions(reader, board):
    """Read schema-41 pair routing, last-used rules and trace relationships.

    Return compatibility inputs for the normalizer alongside the authored
    geometry, using the same point decoder as ordinary traces.
    """
    if reader.header.version <= 40:
        return ()
    read_drc(reader, board, 'LastDRC')
    upgrades = []
    for pair in board.select('DifferentialPairs/DifferentialPair'):
        reader.field_into(pair, 'AutoPadPoints', 'boolean')
        reader.field_into(pair, 'RouteMode', 'integer')
        _extend_side_points(reader, pair)
        for side in ('Pos', 'Neg'):
            upgrades.extend(_separate_traces(reader, pair, side))
    for trace in board.select('Nets/Net/Traces/Trace'):
        reader.field_into(trace, 'PairSeparateTrace', 'integer')
        for end in (1, 2):
            reader.field_into(trace, 'Connected'+str(end), 'integer', replace=True)
        for point in trace.select('Points/Point'):
            reader.field_into(point, 'PairSubPoint', 'integer')
            reader.field_into(point, 'PairNecked', 'boolean')
    for pair in board.select('RemovedDifferentialPairs/RemovedDifferentialPair'):
        _extend_side_points(reader, pair)
    return tuple(upgrades)
