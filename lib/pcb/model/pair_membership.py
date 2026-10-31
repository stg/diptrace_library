"""Ordinary trace geometry identifies its paired center or authored side point."""
from dataclasses import replace

from ...common.reference_edits import preview_references
from ...common.references import ReferenceError
from .relationships import linked
from .routing import ancestor, point_trace
from .pair_routing import center_segment, segment_trace, SEGMENT_TRACES


ROLE = 'pair-point-member'
CONNECTION = 2  # Public differential-center Type: Connection.


def member_center(target):
    if target is None:
        return None
    if (target.kind == 'CenterPoint' and center_segment(target) is not None
            and ancestor(target, 4).kind == 'DifferentialPair'):
        return target
    if (target.kind in ('PosPoint', 'NegPoint') and target.parent is not None
            and target.parent.kind == target.kind[:3]+'Points'):
        center = ancestor(target, 2)
        if (center is not None and center_segment(center) is not None
                and ancestor(center, 4).kind == 'DifferentialPair'):
            return center
    return None


def values(point):
    target = linked(point, ROLE)
    center = member_center(target)
    return (center._ordinal(), target._ordinal() if target is not center else -1) if center else (-1, -1)


def ordinals(point):
    target = linked(point, ROLE)
    center = member_center(target)
    return (center, target) if center is not None and target is not center else (center,) if center else ()


def validate_member(document, source, target):
    trace = point_trace(source)
    center = member_center(target)
    if (trace is None or trace.kind != 'Trace' or source._owner() is not document
            or target._owner() is not document or center is None):
        raise ReferenceError('pair membership requires an ordinary trace point and a paired center or side point')
    segment = center_segment(center)
    if target is center:
        valid = trace in (segment_trace(segment, 'Pos'), segment_trace(segment, 'Neg'))
    else:
        if center.get('Type', 0) == CONNECTION:
            raise ReferenceError('connection membership uses its center, not a side-point selector')
        valid = trace is segment_trace(segment, target.kind[:3])
    if not valid:
        raise ReferenceError('point membership must belong to its segment trace and pair side')


def validate_references(document, references):
    for reference in references:
        if reference.role == ROLE:
            validate_member(document, reference.source, reference.target)


def validate_reference(document, reference, target):
    if reference.role == ROLE:
        if any(link.uid != reference.uid for link in document.references.outgoing(reference.source, role=ROLE)):
            raise ReferenceError('trace point already has a pair membership')
        validate_member(document, reference.source, target)
    elif reference.role in SEGMENT_TRACES:
        with preview_references(document.references, {reference.uid: replace(reference, target=target)}):
            validate_references(document,
                document.references._content_references(reference.source.walk(include_self=True)))


def validate_removal(document, reference):
    if reference.role in SEGMENT_TRACES:
        with preview_references(document.references, {reference.uid: None}):
            validate_references(document,
                document.references._content_references(reference.source.walk(include_self=True)))


def validate_field(document, record, name):
    if record.kind == 'CenterPoint' and name == 'Type':
        validate_references(document, document.references._content_references(record.walk(include_self=True)))
