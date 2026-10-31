"""A center range keeps either a point identity or an explicit unresolved index."""
from ...common.reference_edits import resolve_unavailable_reference
from ...common.references import ReferenceError
from ...common.schema import Field
from .relationships import assign, linked
from .pair_routing import RANGES, center_segment, segment_trace


def missing_name(side, end):
    return 'Unresolved'+side+end+'PointIndex'


def fields(role, side, end):
    missing = missing_name(side, end)

    def selected(node):
        if node.child(missing) is not None:
            raise ReferenceError(f'{side} {end.lower()} range point is unresolved')
        document = node._owner()
        targets = document.references.outgoing(node, role=role) if document is not None else ()
        if len(targets) > 1:
            raise ReferenceError(f'{role}: multiple range targets')
        return targets[0].target if targets else None

    def set_selected(node, target):
        unavailable = node.child(missing)
        if unavailable is None:
            assign(node, role, target)
        else:
            resolve_unavailable_reference(node, target, role=role, missing=unavailable)

    dependencies = dict(reference_dependencies=lambda node: ((node, role, 'outgoing'),),
        collection_dependencies=lambda node: ((node, missing),),
        value_dependencies=lambda node: ((node, missing),) if node.child(missing) is not None else ())

    def index(node):
        if node.child(missing) is not None:
            return node[missing]
        target = selected(node)
        return target._ordinal() if target is not None else -1

    def ordinals(node):
        target = None if node.child(missing) is not None else selected(node)
        return (target,) if target is not None else ()

    return {
        side+end+'Point': Field(side+end+'Point', 'reference', nullable=True,
            getter=selected, setter=set_selected, **dependencies),
        side+'Trace_'+end+'Point': Field(side+'Trace_'+end+'Point', 'integer',
            getter=index, ordinal_dependencies=ordinals, **dependencies),
        missing: Field(missing, 'integer', description='An unavailable current range-point selection.'),
    }


def issue_role(issue):
    return next((role for role in RANGES if issue.message.startswith(role+':')), None)


def issue_fields(issue):
    if (role := issue_role(issue)) is None:
        return ()
    center = issue.source
    segment = center_segment(center)
    if segment is None:
        return ()
    side, _ = RANGES[role]
    return ((segment, segment.schema.fields[side+'Trace']), (center, center.schema.fields['Id']))


def validate_issue(document, issue):
    if (role := issue_role(issue)) is None:
        return
    center = issue.source
    segment = center_segment(center)
    side, end = RANGES[role]
    trace = segment_trace(segment, side) if segment is not None else None
    if (trace is None or issue.collections != (trace.child('Points'),)
            or center.child(missing_name(side, end)) is None):
        raise ReferenceError('resolve or clear the unavailable range before changing its trace scope')
