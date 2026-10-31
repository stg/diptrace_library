"""PCB routing relationships, independent of serialized connection numbers.

Endpoints name a placed pad or a routing point. Its owners supply the format's
object, subobject and point positions. Geometry is edited separately: assigning
an endpoint does not move points or calculate a new route.
"""
from dataclasses import replace

from ...common.references import ReferenceError
from ...common.reference_edits import preview_references
from .membership import component_of, get_net
from .relationships import linked


ENDS = ('trace-end-1', 'trace-end-2')
PAIR_NETS = {'pair-positive': 'Pos', 'pair-negative': 'Neg'}
PAIRED_PADS = {'pair-pad-positive': 'Pos', 'pair-pad-negative': 'Neg'}
PAIR_COLLECTIONS = {'DifferentialPair': 'DifferentialPairs',
                    'RemovedDifferentialPair': 'RemovedDifferentialPairs'}


def is_pair(node):
    return node is not None and node.kind in PAIR_COLLECTIONS


def owned_pair(document, pair):
    """Restorable pair data retains its own Enabled choice, including false."""
    return (is_pair(pair) and pair.parent is document.one('/Board').child(PAIR_COLLECTIONS[pair.kind])
            and (pair.kind == 'RemovedDifferentialPair' or pair['Enabled']))


def ancestor(node, depth):
    for _ in range(depth):
        node = node.parent if node is not None else None
    return node


def pair_net(pair, side):
    return linked(pair, 'pair-positive' if side == 'Pos' else 'pair-negative')


def pad_pair(point):
    pair = ancestor(point, 2)
    return (pair if point.kind == 'PadPoint' and point.parent is not None
            and point.parent.kind == 'PadPoints' and pair is not None
            and is_pair(pair) else None)


def validate_paired_pad(document, source, target, side):
    pair = pad_pair(source)
    if not owned_pair(document, pair):
        raise ReferenceError('paired pad must belong to current pair data in this PCB')
    component = component_of(target)
    if (target.kind != 'Pad' or component is None or target._owner() is not document
            or component.parent is not document.one('/Board/Components') or not component['Enabled']):
        raise ReferenceError('paired pad requires an enabled placed pad in this PCB')
    if get_net(target) is not pair_net(pair, side) or get_net(target) is None:
        raise ReferenceError('paired pad must belong to the corresponding pair net')


def trace_net(trace):
    collection, owner = trace.parent, ancestor(trace, 2)
    if collection is None or owner is None:
        return None
    if trace.kind == 'Trace' and collection.kind == 'Traces' and owner.kind == 'Net':
        return owner
    if (trace.kind in ('PosTrace', 'NegTrace') and
            collection.kind == trace.kind[:3]+'SeparateTraces' and owner.kind == 'DifferentialPair'):
        return pair_net(owner, trace.kind[:3])
    return None


def point_trace(point):
    trace = ancestor(point, 2)
    return trace if point.kind == 'Point' and point.parent is not None and point.parent.kind == 'Points' else None


def endpoint_kind(target):
    if target is None:
        return 'Free'
    if target.kind == 'Pad' and component_of(target) is not None:
        return 'Pad'
    trace = point_trace(target)
    if trace is not None and trace.kind in ('Trace', 'PosTrace', 'NegTrace'):
        return 'Trace' if trace.kind == 'Trace' else 'Separate Trace'
    if (target.kind == 'CenterPoint' and target.parent is not None and target.parent.kind == 'CenterPoints' and
            ancestor(target, 2) is not None and ancestor(target, 2).kind == 'Segment' and
            ancestor(target, 4) is not None and ancestor(target, 4).kind == 'DifferentialPair'):
        return 'Segment'
    if (target.kind in ('PosPoint', 'NegPoint') and target.parent is not None and
            target.parent.kind == target.kind[:3]+'Points' and
            ancestor(target, 2) is not None and ancestor(target, 2).kind == 'CenterPoint' and
            ancestor(target, 4) is not None and ancestor(target, 4).kind == 'Segment' and
            ancestor(target, 6) is not None and ancestor(target, 6).kind == 'DifferentialPair'):
        return 'Segment'
    raise ReferenceError('trace endpoint requires a placed pad or routing point')


def target_net(target):
    kind = endpoint_kind(target)
    if kind == 'Pad':
        return get_net(target)
    if kind in ('Trace', 'Separate Trace'):
        return trace_net(point_trace(target))
    if kind == 'Segment':
        if target.kind == 'CenterPoint':
            return None  # The trace's net selects the side of a shared center point.
        return pair_net(ancestor(target, 6), target.kind[:3])
    return None


def endpoint_values(trace, end):
    """Current object/subobject/point positions; writers encode connection kinds."""
    target = linked(trace, ENDS[end-1])
    kind = endpoint_kind(target)
    if kind == 'Pad':
        return component_of(target)._ordinal(), target._ordinal()+1, -1
    if kind == 'Trace':
        owner = point_trace(target)
        return trace_net(owner)._ordinal(), owner._ordinal(), target._ordinal()
    if kind == 'Separate Trace':
        return -1, point_trace(target)._ordinal(), target._ordinal()
    if kind == 'Segment':
        if target.kind == 'CenterPoint':
            return ancestor(target, 2)._ordinal(), target._ordinal(), -1
        return ancestor(target, 4)._ordinal(), ancestor(target, 2)._ordinal(), target._ordinal()
    return -1, -1, -1


def endpoint_ordinals(trace, end):
    target = linked(trace, ENDS[end-1])
    kind = endpoint_kind(target)
    if kind == 'Pad':
        return component_of(target), target
    if kind == 'Trace':
        owner = point_trace(target)
        return trace_net(owner), owner, target
    if kind == 'Separate Trace':
        return point_trace(target), target
    if kind == 'Segment':
        if target.kind == 'CenterPoint':
            return ancestor(target, 2), target
        return ancestor(target, 4), ancestor(target, 2), target
    return ()


def _net_in(document, net):
    if net is None or net.kind != 'Net' or net.parent is not document.one('/Board/Nets'):
        raise ReferenceError('trace requires a net in this PCB')
    if not net['Enabled']:
        raise ReferenceError('trace requires an enabled net')


def validate_endpoint(document, source, target):
    net = trace_net(source)
    _net_in(document, net)
    if target._owner() is not document:
        raise ReferenceError('trace endpoint is outside this PCB')
    if endpoint_kind(target) == 'Pad':
        component = component_of(target)
        if component.parent is not document.one('/Board/Components') or not component['Enabled']:
            raise ReferenceError('trace endpoint requires an enabled placed component')
    if target.kind == 'CenterPoint' and endpoint_kind(target) == 'Segment':
        pair = ancestor(target, 4)
        if net in (pair_net(pair, 'Pos'), pair_net(pair, 'Neg')):
            return
    if target_net(target) is not net:
        raise ReferenceError('trace endpoint and target must belong to the same net')


def check_pad_net(document, pad, net):
    from .length_matching import check_pad_net as check_length_net
    check_length_net(document, pad, net)
    for link in document.references.incoming(pad):
        if link.role in ENDS and trace_net(link.source) is not net:
            raise ReferenceError('net change would contradict an attached trace; edit its endpoint first')
        if link.role in PAIRED_PADS and pair_net(pad_pair(link.source), PAIRED_PADS[link.role]) is not net:
            raise ReferenceError('net change would contradict a paired pad; edit the pair assignment first')


def validate_retarget(document, reference, target):
    role = reference.role
    if role not in (*ENDS, *PAIR_NETS, *PAIRED_PADS):
        return
    if any(link.uid != reference.uid for link in document.references.outgoing(reference.source, role=role)):
        raise ReferenceError(f'{role}: record already has a target')
    if role in PAIRED_PADS:
        validate_paired_pad(document, reference.source, target, PAIRED_PADS[role])
    elif role in ENDS:
        validate_endpoint(document, reference.source, target)
    else:
        _net_in(document, target)
        pair = reference.source
        if not owned_pair(document, pair):
            raise ReferenceError('differential pair must belong to this PCB')
        with preview_references(document.references, {reference.uid: replace(reference, target=target)}):
            validate_references(document, document.references._content_references(pair.walk(include_self=True)))


def validate_move(document, node, parent):
    if pad_pair(node) is not None and (parent.kind != 'PadPoints' or not owned_pair(document, parent.parent)):
        raise ReferenceError('paired pad row must remain in a differential pair in this PCB')
    if node.kind == 'Trace' and (parent.kind != 'Traces' or parent.parent is None or
            parent.parent.kind != 'Net' or parent.parent.parent is not document.one('/Board/Nets')):
        raise ReferenceError('trace must remain in a PCB net')
    if node.kind == 'Trace':
        _net_in(document, parent.parent)
    if node.kind in ('PosTrace', 'NegTrace') and (parent.kind != node.kind[:3]+'SeparateTraces' or
            parent.parent is None or parent.parent.kind != 'DifferentialPair'):
        raise ReferenceError('separate trace must remain on its differential-pair side')
    if node.kind == 'DifferentialPair' and parent is not document.one('/Board').child('DifferentialPairs'):
        raise ReferenceError('differential pair must remain in this PCB')
    if node.kind == 'RemovedDifferentialPair' and parent is not document.one('/Board').child('RemovedDifferentialPairs'):
        raise ReferenceError('removed pair must remain in this PCB')


def validate_references(document, references):
    for link in references:
        if link.role in ENDS:
            validate_endpoint(document, link.source, link.target)
        elif link.role in PAIR_NETS:
            _net_in(document, link.target)
        elif link.role in PAIRED_PADS:
            validate_paired_pad(document, link.source, link.target, PAIRED_PADS[link.role])


def validate(document):
    validate_references(document, document.references)
