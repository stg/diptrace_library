"""Consume saved routing keys into the PCB model's endpoint identities.

This is one import-assembly stage, not the complete DIP reader. Its dictionaries
are temporary lookups for subsequent binding and modernization stages.
"""
from dataclasses import dataclass

from ....common.model import Element
from ....common.structural_edits import assembly
from ....common.references import Index
from ....common.conversion import import_notice
from ...model import routing_records
from ...model.routing import ENDS, PAIRED_PADS
from ..connection_types import CONNECTION_NAMES
from .assemble import CoreAssembly, assemble_core
from ..errors import PcbError
from ..routing_values import UNAVAILABLE_PHASE_BOUNDARY
from .pair_routing import prepare_segments, prepare_peers, prepare_segment_ends, prepare_memberships
from .trace_cleanup import normalize_traces
from .pair_refresh import refresh_members


@dataclass(frozen=True)
class RoutingAssembly:
    core: CoreAssembly
    traces: dict[tuple[int, int], Element]
    separate_traces: dict[tuple[Element, str, int], Element]

    @property
    def document(self):
        return self.core.document


def _indexed(upgrades):
    result = {}
    for upgrade in upgrades:
        key = upgrade.previous_number
        if key in result:
            raise PcbError(f'ambiguous saved trace key {key}')
        result[key] = upgrade.trace
    return result


def _at(collection, kind, index):
    rows = collection.children(kind) if collection is not None else ()
    return rows[index] if 0 <= index < len(rows) else None


def assemble_routing(decoded, core=None):
    """Resolve endpoints before discarding the superseded connection tuples."""
    core = assemble_core(decoded) if core is None else core
    board = decoded.board
    by_net = {net: key for key, net in core.nets.items()}
    traces = {(by_net[upgrade.net], key): trace
              for upgrade in decoded.upgrades.nets
              if upgrade.net in by_net
              for key, trace in _indexed(upgrade.traces).items()}
    traces = normalize_traces(core, traces)
    ordinary = tuple(traces.values())
    separate = {}
    pair_nets, paired_pads, consumed_pads, trace_scopes, net_scopes = [], [], [], {}, {}
    saved_pairs = board.select('DifferentialPairs/DifferentialPair')
    inactive_pairs = [pair for pair in saved_pairs if not pair['Enabled']]
    pairs = [pair for pair in saved_pairs if pair['Enabled']]
    removed_pairs = board.select('RemovedDifferentialPairs/RemovedDifferentialPair')
    all_pairs = (*pairs, *removed_pairs)
    segment_links, segment_slots, unresolved_ranges = prepare_segments(pairs, traces)
    peer_links, peer_slots = prepare_peers(pairs, traces)
    inferred = refresh_members(decoded, core, traces, pairs, segment_links, peer_links)
    separate_keys = {upgrade.trace: upgrade.previous_number for upgrade in decoded.upgrades.separate_traces
                     if upgrade.trace.parent.parent in pairs}
    for pair in all_pairs:
        for side, role in (('Pos', 'pair-positive'), ('Neg', 'pair-negative')):
            key = pair[side+'Net']
            net = core.nets.get(key)
            if net is None:
                raise PcbError(f'unresolved saved differential-pair net key {key}')
            pair_nets.append((pair, role, net))
            pad_role = next(role for role, name in PAIRED_PADS.items() if name == side)
            for row in pair.select('PadPoints/PadPoint'):
                if row in inferred:
                    target = inferred[row][0 if side == 'Pos' else 1]
                    paired_pads.append((row, pad_role, target))
                    consumed_pads.extend(slot for name in (side+'Comp', side+'Pad')
                                         if (slot := row.child(name)) is not None)
                    continue
                component_slot, pad_slot = row.one(side+'Comp'), row.one(side+'Pad')
                key = component_slot.values[0], pad_slot.values[0]
                if key != (-1, -1):
                    target = core.pads.get(key)
                    if target is None:
                        raise PcbError(f'unresolved saved paired pad key {key}')
                    if target['Net'] is not net:
                        raise PcbError('saved paired pad contradicts its pair net')
                    paired_pads.append((row, pad_role, target))
                consumed_pads.extend((component_slot, pad_slot))
            if pair.kind == 'RemovedDifferentialPair':
                continue
            net_scopes.setdefault(net, []).append((pair, side))
            for trace in pair.select(side+'SeparateTraces/'+side+'Trace'):
                saved = separate_keys[trace]
                if (pair, side, saved) in separate:
                    raise PcbError(f'ambiguous saved separate trace key {saved}')
                separate[pair, side, saved] = trace
                trace_scopes[trace] = pair, side, net

    def scope(trace):
        if trace in trace_scopes:
            pair, side, _ = trace_scopes[trace]
            return pair, side
        scopes = net_scopes.get(trace.parent.parent, ())
        if len(scopes) != 1:
            raise PcbError('differential endpoint does not identify one pair side')
        return scopes[0]

    endpoints = []
    all_traces = (*ordinary, *separate_keys)
    for trace in all_traces:
        for end in (1, 2):
            kind = CONNECTION_NAMES.get(trace['Connected'+str(end)])
            values = tuple(trace[name+str(end)] for name in ('Object', 'SubObject', 'Point'))
            obj, sub, point = values
            if kind == 'Free':
                continue
            if kind == 'Pad':
                target = core.pads.get((obj, sub))
            elif kind == 'Trace':
                owner = traces.get((obj, sub))
                target = _at(owner.child('Points') if owner is not None else None, 'Point', point)
            elif kind == 'Segment':
                pair, side = scope(trace)
                segment = _at(pair.child('Segments'), 'Segment', obj)
                center = _at(segment.child('CenterPoints') if segment is not None else None, 'CenterPoint', sub)
                target = (center if point < 0 else _at(
                    center.child(side+'Points') if center is not None else None, side+'Point', point))
            elif kind == 'Separate Trace':
                pair, side = scope(trace)
                owner = separate.get((pair, side, sub))
                target = _at(owner.child('Points') if owner is not None else None, 'Point', point)
            else:
                raise PcbError(f'unimplemented trace connection kind {trace["Connected"+str(end)]}')
            if target is None:
                raise PcbError(f'unresolved saved {kind} endpoint {values}')
            endpoints.append((trace, ENDS[end-1], target))

    end_links, end_slots = prepare_segment_ends(all_pairs)
    member_links, member_slots = prepare_memberships(traces, segment_links)
    restored_links, restored_slots, restored_ranges = prepare_segments(removed_pairs, traces)
    segment_links.extend(restored_links)
    segment_slots.extend(restored_slots)
    unresolved_ranges.extend(restored_ranges)
    document = core.document
    with assembly(document):
        for pair in inactive_pairs:
            pair.detach()
        removed = board.child('RemovedDifferentialPairs')
        if removed is not None and not removed.arguments and not removed.children():
            # An empty source collection contains no current pair facts.
            removed.detach()
        # Text and binary serialize the unavailable calculation marker with
        # different magnitudes. It is absence, not a second kind of length.
        for trace in all_traces:
            for point in trace.one('Points').children('Point'):
                for name in ('PhaseFwd', 'PhaseBack'):
                    if (value := point.get(name)) is not None and value <= UNAVAILABLE_PHASE_BOUNDARY:
                        point.one(name).detach()
        for slot in (*consumed_pads, *segment_slots, *peer_slots, *end_slots, *member_slots):
            slot.detach()
        for center, role, name, index, points in unresolved_ranges:
            center.add(name, index)
        for node in board.walk(include_self=True):
            schema = routing_records.definition(node)
            if schema is not None:
                if schema.parameters == ('Id',):
                    node.set_values()
                node.bind_schema(schema)
        for pair in all_pairs:
            for name in ('Number', 'PosNet', 'NegNet'):
                pair.one(name).detach()
        for trace in all_traces:
            for end in (1, 2):
                for name in ('Connected', 'Object', 'SubObject', 'Point'):
                    trace.one(name+str(end)).detach()
        with document.references.binding_batch():
            for source, role, target in (*pair_nets, *paired_pads, *endpoints, *segment_links,
                                        *peer_links, *end_links, *member_links):
                document.references.bind(source, target, role=role, preserve=True)
            for center, role, name, index, points in unresolved_ranges:
                document.references.note(center, role+': range point cannot be resolved',
                    Index(center.one(name)), collections=(points,))
    if unresolved_ranges:
        import_notice('warning', 'unresolved-pair-range',
            'Differential center ranges refer to unavailable trace points',
            tuple(dict.fromkeys(row[0] for row in unresolved_ranges)))
    if inactive_pairs:
        import_notice('info', 'inactive-differential-pairs', 'Discarded inactive differential-pair records.',
                      (board.one('DifferentialPairs'),))
    return RoutingAssembly(core, traces, separate)
