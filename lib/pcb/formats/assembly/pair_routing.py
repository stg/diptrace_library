"""Consume saved segment trace keys and center range positions before binding."""
from ...model.pair_routing import SEGMENT_TRACES, SEGMENT_ENDS, RANGES, PEER
from ...model.pair_membership import ROLE as MEMBER, CONNECTION
from ...model.pair_ranges import missing_name
from ..errors import PcbError


def _integer(slot):
    if len(slot.values) != 1 or type(slot.values[0]) is not int or slot.children():
        raise PcbError(f'{slot.path}: expected one integer selector')
    return slot.values[0]


def prepare_segments(pairs, traces):
    """Preflight all known selectors without modifying the adapter-owned input."""
    links, consumed, unresolved = [], [], []
    for pair in pairs:
        for segment in pair.select('Segments/Segment'):
            for center in segment.select('CenterPoints/CenterPoint'):
                if (direction := center.child('Orientation')) is not None:
                    _integer(direction)
                    consumed.append(direction)
            for role, side in SEGMENT_TRACES.items():
                slot = segment.child(side+'Trace')
                key = _integer(slot) if slot is not None else -1
                trace = traces.get((pair[side+'Net'], key)) if key >= 0 else None
                if key >= 0 and trace is None:
                    raise PcbError(f'unresolved saved segment {side} trace key {key}')
                if slot is not None:
                    consumed.append(slot)
                if trace is not None:
                    links.append((segment, role, trace))
                points = trace.one('Points')._child_sequence('Point') if trace is not None else ()
                for center in segment.select('CenterPoints/CenterPoint'):
                    for range_role, (range_side, end) in RANGES.items():
                        if range_side != side:
                            continue
                        field = center.child(side+'Trace_'+end+'Point')
                        if field is None:
                            continue
                        index = _integer(field)
                        if index >= 0:
                            if index >= len(points):
                                if trace is None:
                                    raise PcbError(f'unresolved saved center {side} {end} trace scope')
                                unresolved.append((center, range_role, missing_name(side, end), index,
                                                   trace.one('Points')))
                            else:
                                links.append((center, range_role, points[index]))
                        consumed.append(field)
    return links, consumed, unresolved


def prepare_peers(pairs, traces):
    """Resolve separate->ordinary keys, consuming the redundant inverse cache."""
    links, consumed, by_ordinary = [], [], {}
    for pair in pairs:
        for side in ('Pos', 'Neg'):
            for separate in pair.select(side+'SeparateTraces/'+side+'Trace'):
                slot = separate.child('TraceId')
                if slot is None:
                    continue
                key = _integer(slot)
                consumed.append(slot)
                if key < 0:
                    continue
                ordinary = traces.get((pair[side+'Net'], key))
                if ordinary is None:
                    raise PcbError(f'unresolved saved separate-trace peer key {key}')
                if ordinary in by_ordinary:
                    raise PcbError('multiple separate traces identify the same ordinary peer')
                by_ordinary[ordinary] = separate
                links.append((separate, PEER, ordinary))
    for ordinary in traces.values():
        slot = ordinary.child('PairSeparateTrace')
        if slot is None:
            continue
        _integer(slot)
        # The ordinary backlink is a derived view, cleared for segment traces
        # during loading. It is not another independently editable relationship.
        consumed.append(slot)
    return links, consumed


def prepare_segment_ends(pairs):
    """Bind paired-pad ends or another segment's center by current positions."""
    links, consumed = [], []
    for pair in pairs:
        segments = pair.select('Segments/Segment')
        pads = pair.select('PadPoints/PadPoint')
        for segment in segments:
            for role, end in SEGMENT_ENDS.items():
                point_slot, segment_slot = segment.child(end+'Point'), segment.child(end+'Segment')
                point = _integer(point_slot) if point_slot is not None else -1
                owner = _integer(segment_slot) if segment_slot is not None else -1
                if point >= 0:
                    if owner < 0:
                        choices = pads
                    else:
                        choices = (segments[owner].one('CenterPoints')._child_sequence('CenterPoint')
                                   if owner < len(segments) else ())
                    if point >= len(choices):
                        raise PcbError(f'unresolved saved segment {end} target {(owner, point)}')
                    links.append((segment, role, choices[point]))
                consumed.extend(slot for slot in (point_slot, segment_slot) if slot is not None)
    return links, consumed


def prepare_memberships(traces, segment_links):
    """Consume center/side selectors; connection subselectors are generated counters."""
    scopes = {}
    for segment, role, trace in segment_links:
        if role in SEGMENT_TRACES:
            scopes.setdefault(trace, []).append((segment, SEGMENT_TRACES[role]))
    links, consumed = [], []
    for trace in traces.values():
        for point in trace.one('Points')._child_sequence('Point'):
            center_slot, side_slot = point.child('PairPoint'), point.child('PairSubPoint')
            ci = _integer(center_slot) if center_slot is not None else -1
            sub = _integer(side_slot) if side_slot is not None else -1
            owners = scopes.get(trace, ())
            # Pair selectors are interpreted only for a trace supplying segment
            # geometry. Other traces can retain unused tags after editing.
            if ci >= 0 and owners:
                if len(owners) != 1:
                    raise PcbError('paired point does not identify one owning segment and side')
                segment, side = owners[0]
                centers = segment.one('CenterPoints')._child_sequence('CenterPoint')
                if ci >= len(centers):
                    raise PcbError(f'unresolved saved point center {ci}')
                target = centers[ci]
                if target.get('Type', 0) != CONNECTION and sub >= 0:
                    points = target.one(side+'Points')._child_sequence(side+'Point')
                    if sub >= len(points):
                        raise PcbError(f'unresolved saved {side} side-point membership {sub}')
                    target = points[sub]
                links.append((point, MEMBER, target))
            consumed.extend(slot for slot in (center_slot, side_slot) if slot is not None)
    return links, consumed
