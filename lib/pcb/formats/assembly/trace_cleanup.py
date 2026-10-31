"""Normalize unusable saved traces before binding their current identities."""
from collections import deque
from decimal import Decimal, localcontext

from ....common.conversion import import_notice
from ....common.geometry import decimal_precision
from ....common.structural_edits import assembly
from ..connection_types import CONNECTION_NAMES


MIN_TRACE_LENGTH = Decimal('.001')


def _short(points):
    values = tuple(Decimal(str(point[name])) for point in points for name in ('X', 'Y'))
    with localcontext() as context:
        context.prec = 2*decimal_precision(values)
        x1, y1, x2, y2 = values
        return (x2-x1)**2+(y2-y1)**2 < MIN_TRACE_LENGTH**2


def _pair_selections(board, removed):
    for path in ('DifferentialPairs/DifferentialPair', 'RemovedDifferentialPairs/RemovedDifferentialPair'):
        for pair in board.select(path):
            for side in ('Pos', 'Neg'):
                net = pair[side+'Net']
                for segment in pair.select('Segments/Segment'):
                    key = segment.get(side+'Trace', -1)
                    if key >= 0 and (net, key) in removed:
                        segment.one(side+'Trace').set_values(-1)
                        for center in segment.select('CenterPoints/CenterPoint'):
                            for end in ('Start', 'End'):
                                slot = center.child(side+'Trace_'+end+'Point')
                                if slot is not None:
                                    slot.set_values(-1)
                for trace in pair.select(side+'SeparateTraces/'+side+'Trace'):
                    key = trace.get('TraceId', -1)
                    if key >= 0 and (net, key) in removed:
                        trace.one('TraceId').set_values(-1)


def normalize_traces(core, traces):
    """Remove invalid paths and unused short free-ended stubs to a stable result.

    Saved keys are temporary input selectors. Resolve dependencies using those
    keys, then let ordinary relationship binding regenerate current positions.
    A tiny path used by another ordinary trace is retained. Removing a path with
    fewer than two points instead frees its dependants without moving geometry.
    """
    by_trace = {trace: key for key, trace in traces.items()}
    active = set(by_trace)
    incoming = {trace: set() for trace in active}
    targets = {}
    board = core.document.one('/Board')
    separate = tuple(board.select('DifferentialPairs/DifferentialPair/PosSeparateTraces/PosTrace')
                     + board.select('DifferentialPairs/DifferentialPair/NegSeparateTraces/NegTrace'))
    for trace in (*by_trace, *separate):
        for end in ('1', '2'):
            if CONNECTION_NAMES.get(trace['Connected'+end]) != 'Trace':
                continue
            target = traces.get((trace['Object'+end], trace['SubObject'+end]))
            if target is not None:
                targets[trace, end] = target
                incoming[target].add((trace, end))

    pending = deque(reversed(tuple(by_trace)))
    removed = []
    with assembly(core.document):
        while pending:
            trace = pending.popleft()
            if trace not in active:
                continue
            points = trace.one('Points')._child_sequence('Point')
            if len(points) >= 2:
                if (len(points) != 2 or
                        not any(CONNECTION_NAMES.get(trace['Connected'+end]) == 'Free' for end in ('1', '2')) or
                        any(owner in active and owner is not trace for owner, _ in incoming[trace]) or
                        not _short(points)):
                    continue
            active.remove(trace)
            removed.append(trace)
            # A deleted path cannot remain a positional target. Its neighbours
            # keep their coordinates and may themselves become unused stubs.
            for source, end in tuple(incoming[trace]):
                source.one('Connected'+end).set_values(-1)
                targets.pop((source, end), None)
                incoming[trace].discard((source, end))
                if source in active:
                    pending.append(source)
            for end in ('1', '2'):
                target = targets.pop((trace, end), None)
                if target is not None:
                    incoming[target].discard((trace, end))
                    if target in active:
                        pending.append(target)
        if removed:
            import_notice('info', 'unusable-trace-normalization',
                'Removed unusable paths and unused short free-ended traces.', removed,
                recoverability='surviving geometry remains; references to removed paths become unassigned')
            removed_keys = {by_trace[trace] for trace in removed}
            _pair_selections(board, removed_keys)
            for trace in removed:
                net, _ = by_trace[trace]
                for row in trace.select('ConnectedTeardrops/Item'):
                    polygon = core.teardrops.pop((net, row.values[0]), None)
                    if polygon is not None:
                        polygon.detach()
                trace.detach()
    return {key: trace for key, trace in traces.items() if trace in active}
