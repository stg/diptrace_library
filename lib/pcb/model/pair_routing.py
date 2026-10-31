"""Differential segment traces and their center-point ranges use identities."""
from dataclasses import replace

from ...common.reference_edits import preview_references
from ...common.references import ReferenceError
from .relationships import linked
from .routing import PAIR_NETS, ancestor, pair_net, pad_pair, point_trace, trace_net, is_pair, owned_pair


SEGMENT_TRACES = {'pair-segment-positive': 'Pos', 'pair-segment-negative': 'Neg'}
RANGES = {f'pair-range-{side.lower()}-{end.lower()}': (side, end)
          for side in ('Pos', 'Neg') for end in ('Start', 'End')}
PEER = 'pair-trace-peer'
SEGMENT_ENDS = {'pair-segment-start': 'Start', 'pair-segment-end': 'End'}


def segment_end_values(segment, role):
    target = linked(segment, role)
    if target is None:
        return -1, -1
    owner = center_segment(target)
    return target._ordinal(), owner._ordinal() if owner is not None else -1


def segment_end_ordinals(segment, role):
    target = linked(segment, role)
    if target is None:
        return ()
    owner = center_segment(target)
    return (target, owner) if owner is not None else (target,)


def separate_peer(trace):
    document = trace._owner()
    links = document.references.incoming(trace, role=PEER) if document else ()
    if len(links) > 1:
        raise ReferenceError('ordinary trace has multiple separate-trace peers')
    return links[0].source if links else None


def segment_pair(segment):
    pair = ancestor(segment, 2)
    return (pair if segment.kind == 'Segment' and segment.parent is not None
            and segment.parent.kind == 'Segments' and pair is not None
            and is_pair(pair) else None)


def center_segment(center):
    segment = ancestor(center, 2)
    return (segment if center.kind == 'CenterPoint' and center.parent is not None
            and center.parent.kind == 'CenterPoints' and segment is not None
            and segment_pair(segment) is not None else None)


def segment_trace(segment, side):
    role = next(role for role, name in SEGMENT_TRACES.items() if name == side)
    return linked(segment, role)


def _placed_pair(document, pair, subject='segment'):
    if not owned_pair(document, pair):
        raise ReferenceError(f'{subject} must belong to current pair data in this PCB')


def validate_peer(document, source, target, uid):
    pair = ancestor(source, 2)
    if (source.kind not in ('PosTrace', 'NegTrace') or source.parent is None
            or source.parent.kind != source.kind[:3]+'SeparateTraces'):
        raise ReferenceError('peer source must be a separate differential trace')
    _placed_pair(document, pair, 'separate trace')
    if (target._owner() is not document or target.kind != 'Trace'
            or trace_net(target) is not trace_net(source) or trace_net(target) is None):
        raise ReferenceError('trace peer must belong to the corresponding pair net')
    if any(link.uid != uid for link in document.references.incoming(target, role=PEER)):
        raise ReferenceError('ordinary trace already has a separate-trace peer')


def validate_end(document, source, target):
    pair = segment_pair(source)
    _placed_pair(document, pair)
    center_owner = center_segment(target)
    target_pair = segment_pair(center_owner) if center_owner is not None else pad_pair(target)
    if target._owner() is not document or target_pair is not pair:
        raise ReferenceError('segment end requires a paired pad or center point in the same pair')


def validate_trace(document, source, target, side):
    pair = segment_pair(source)
    _placed_pair(document, pair)
    if (target._owner() is not document or target.kind != 'Trace'
            or trace_net(target) is not pair_net(pair, side) or trace_net(target) is None):
        raise ReferenceError('segment trace must belong to the corresponding pair net')


def validate_range(document, source, target, side):
    segment = center_segment(source)
    _placed_pair(document, segment_pair(segment) if segment is not None else None)
    if (target._owner() is not document or target.kind != 'Point'
            or point_trace(target) is not segment_trace(segment, side)
            or point_trace(target) is None):
        raise ReferenceError('center range point must belong to its segment trace')


def validate_references(document, references):
    for reference in references:
        if reference.role in SEGMENT_TRACES:
            validate_trace(document, reference.source, reference.target, SEGMENT_TRACES[reference.role])
        elif reference.role in RANGES:
            validate_range(document, reference.source, reference.target, RANGES[reference.role][0])
        elif reference.role == PEER:
            validate_peer(document, reference.source, reference.target, reference.uid)
        elif reference.role in SEGMENT_ENDS:
            validate_end(document, reference.source, reference.target)


def validate_reference(document, reference, target):
    role = reference.role
    if role not in (*SEGMENT_TRACES, *RANGES, *PAIR_NETS, *SEGMENT_ENDS, PEER):
        return
    if role not in PAIR_NETS and any(link.uid != reference.uid for link in
            document.references.outgoing(reference.source, role=role)):
        raise ReferenceError(f'{role}: record already has a target')
    if role in SEGMENT_ENDS:
        validate_end(document, reference.source, target)
    elif role == PEER:
        validate_peer(document, reference.source, target, reference.uid)
    elif role in RANGES:
        from .pair_ranges import missing_name
        if reference.source.child(missing_name(*RANGES[role])) is not None:
            raise ReferenceError('resolve the unavailable range through its point field')
        validate_range(document, reference.source, target, RANGES[role][0])
    else:
        if role in SEGMENT_TRACES:
            validate_trace(document, reference.source, target, SEGMENT_TRACES[role])
        with preview_references(document.references, {reference.uid: replace(reference, target=target)}):
            validate_references(document,
                document.references._content_references(reference.source.walk(include_self=True)))


def validate_removal(document, reference):
    if reference.role in (*SEGMENT_TRACES, *PAIR_NETS):
        with preview_references(document.references, {reference.uid: None}):
            validate_references(document,
                document.references._content_references(reference.source.walk(include_self=True)))


def validate_move(document, node, parent):
    if segment_pair(node) is not None:
        if parent.kind != 'Segments' or parent.parent is None:
            raise ReferenceError('segment must remain in a differential pair')
        _placed_pair(document, parent.parent)
    elif center_segment(node) is not None:
        if parent.kind != 'CenterPoints' or parent.parent is None:
            raise ReferenceError('center point must remain in a differential segment')
        _placed_pair(document, segment_pair(parent.parent))
