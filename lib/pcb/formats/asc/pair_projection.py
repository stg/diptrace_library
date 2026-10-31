"""Current differential relationships and supplied geometry projected to ASC."""
from ....common.conversion import warn
from ....common.model import Element
from ...model import routing_records as model
from ...model.pair_ranges import missing_name
from ..output_indices import OutputIndices, pad_number
from ..routing_projection import center_directions
from . import routing_columns as columns
from .net_projection import project_trace, warn_shield_group
from .projection import check, collection, fields, flag, rows, value


def _side_points(center, side, output, report):
    source = center.child(side+'Points')
    actual = () if source is None else rows(source, model.COLLECTIONS[side+'Points'], model.SIDE_POINT)
    target = output.add(side+'Points', len(actual))
    for point in actual:
        warn_shield_group(point, report)
        target.add('pt', *(flag(value(point, name)) if name in columns.FLAGS else value(point, name)
                           for name in columns.SIDE_POINT))


def _segment(segment, report):
    check(segment, model.SEGMENT)
    output = Element('Segment')
    for side in ('Pos', 'Neg'):
        output.add(side+'Line', segment[side+'TraceIndex'])
    for end in ('Start', 'End'):
        for name in ('Point', 'Segment'):
            output.add(end+name, segment[end+name])
    centers = output.add('CenterPoints')
    actual = rows(segment.one('CenterPoints'), model.COLLECTIONS['CenterPoints'], model.CENTER)
    unavailable = tuple(missing_name(side, end) for side in ('Pos', 'Neg') for end in ('Start', 'End'))
    shields = ('PosShieldGroup', 'NegShieldGroup')
    for center, direction in zip(actual, center_directions(actual)):
        target = centers.add('CenterPoint')
        fields(center, target, exclude=unavailable+shields, names={'PosTraceSide': 'PosLineSide'})
        if any(value(center, name) != -1 for name in shields):
            warn(report, 'pair-shield-group', 'asc',
                 'PCB ASC cannot represent differential center shield-group membership', (center,))
        target.add('Layer', center['Lay'])
        target.add('ViaStyle', center['ViaStyle'])
        target.add('Orientation', direction)
        for side in ('Pos', 'Neg'):
            for end in ('Start', 'End'):
                target.add(side+'Line_'+end+'Point', center[side+'Trace_'+end+'Point'])
            _side_points(center, side, target, report)
        if any(center.child(name) is not None for name in unavailable):
            warn(report, 'unresolved-pair-range', 'asc',
                 'Retained a differential center range whose point cannot be resolved', (center,),
                 recoverability='current range index and trace scope retained')
    return output


def project_pairs(board, *, indices=None, report=None, removed=False):
    indices = indices or OutputIndices(board)
    kind = 'RemovedDifferentialPair' if removed else 'DifferentialPair'
    schema = model.REMOVED_PAIR if removed else model.PAIR
    output = Element(kind+'s')
    for pair in collection(board, kind+'s', model.COLLECTIONS[kind+'s'], schema):
        target = output.add(kind, pair['Name'])
        fields(pair, target, exclude=('Name',), names={'AutoPadPoints': 'PadPoints_Auto'})
        target.add('Number', pair['Id'])
        target.add('NetClass', indices.class_number(pair['Class']))
        for side in ('Pos', 'Neg'):
            target.add(side+'Net', pair[side+'NetIndex'])
        actual = collection(pair, 'PadPoints', model.COLLECTIONS['PadPoints'], model.PAIRED_PAD)
        pads = target.add('PadPoints', len(actual))
        for row in actual:
            pads.add('pt', row['PosComponentIndex'], pad_number(row['PosPad']),
                     row['NegComponentIndex'], pad_number(row['NegPad']))
        segments = target.add('Segments')
        for segment in collection(pair, 'Segments', model.COLLECTIONS['Segments'], model.SEGMENT):
            segments.append(_segment(segment, report))
        for side in (() if removed else ('Pos', 'Neg')):
            traces = target.add('SeparateLines_'+side)
            for trace in collection(pair, side+'SeparateTraces', model.COLLECTIONS[side+'SeparateTraces'],
                                    model.SEPARATE_TRACE):
                traces.append(project_trace(trace, separate=True, report=report))
    return output
