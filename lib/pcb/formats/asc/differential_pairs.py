"""Expand current public ASC differential-pair geometry before shared binding."""
from ...model.routing_records import SIDE_POINT
from ..errors import PcbError
from .routing import unpack_trace
from .values import booleans, counted_rows, numeric_row, rename
from . import routing_columns as columns


def _side_points(container, side):
    for index, row in enumerate(counted_rows(container)):
        values = numeric_row(row, len(columns.SIDE_POINT),
                             flags=columns.indices(columns.SIDE_POINT, columns.FLAGS),
                             integers=columns.indices(columns.SIDE_POINT, columns.INTEGERS))
        row.kind = side+'Point'
        row.set_values(index)
        for name, value in zip(columns.SIDE_POINT, values):
            definition = SIDE_POINT.fields[name]
            try:
                if not definition.readonly:
                    definition.validate(value.value)
            except (ValueError, TypeError) as error:
                raise PcbError(f'{row.path}/{name}: {error}') from error
            row.add(name, value)


def unpack_pairs(board, *, removed=False):
    """Return temporary separate-trace keys; all geometry stays in the input tree."""
    kind = 'RemovedDifferentialPair' if removed else 'DifferentialPair'
    collection = board.child(kind+'s')
    if collection is None:
        return ()
    separate = []
    for index, pair in enumerate(collection.children()):
        if (pair.kind != kind or len(pair.values) != 1
                or not isinstance(pair.values[0], str) or pair.child('Name') is not None):
            raise PcbError(f'{pair.path}: expected one differential-pair name')
        if any(pair.child(name) is None for name in ('PadPoints', 'Segments')):
            raise PcbError(f'{pair.path}: expected paired-pad and segment sections')
        pair.add('Name', pair.arguments[0])
        pair.set_values(index)
        if not removed:
            rename(pair, {'PadPoints_Auto': 'AutoPadPoints', 'SeparateLines_Pos': 'PosSeparateTraces',
                          'SeparateLines_Neg': 'NegSeparateTraces'})
        booleans(pair, ('Enabled', 'CustomColor') if removed else ('Enabled', 'CustomColor', 'AutoPadPoints'))
        for position, row in enumerate(counted_rows(pair.one('PadPoints'))):
            values = numeric_row(row, 4, integers=range(4))
            row.kind = 'PadPoint'
            row.set_values(position)
            for name, value in zip(('PosComp', 'PosPad', 'NegComp', 'NegPad'), values):
                row.add(name, value)
        for position, segment in enumerate(pair.one('Segments').children()):
            if segment.kind != 'Segment' or segment.values:
                raise PcbError(f'{segment.path}: expected a differential segment')
            segment.set_values(position)
            rename(segment, {'PosLine': 'PosTrace', 'NegLine': 'NegTrace'})
            for ci, center in enumerate(segment.one('CenterPoints').children()):
                if center.kind != 'CenterPoint' or center.values:
                    raise PcbError(f'{center.path}: expected a center point')
                center.set_values(ci)
                rename(center, {'Layer': 'Lay', 'PosLineSide': 'PosTraceSide',
                    **{side+'Line_'+end+'Point': side+'Trace_'+end+'Point'
                       for side in ('Pos', 'Neg') for end in ('Start', 'End')}})
                booleans(center, ('Necked', 'Selected', 'PhaseError'))
                for side in ('Pos', 'Neg'):
                    _side_points(center.one(side+'Points'), side)
        for side in (() if removed else ('Pos', 'Neg')):
            for trace in pair.one(side+'SeparateTraces').children():
                if trace.kind != 'Line_'+side:
                    raise PcbError(f'{trace.path}: expected a {side} separate trace')
                trace.kind = side+'Trace'
                separate.append(unpack_trace(trace, separate=True))
    return tuple(separate)
