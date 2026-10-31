"""PCB pad assignments and explicit net member lists share identity links.

An explicit member owns the assignment for a listed pad. A pad may also have a
net assignment without an entry in the net's pad list; that uses a direct link.
Neither representation stores a second numeric copy of the assigned net.
"""
from ...common.model import Element
from ...common.references import ReferenceError
from ...common.schema import Field, Record


def member_pad(member):
    document = member._owner()
    links = document.references.outgoing(member, role='net-member') if document else ()
    if len(links) != 1:
        raise ReferenceError('net member does not have one resolved pad')
    return links[0].target


def component_of(pad):
    pattern = pad.parent.parent if pad.parent is not None else None
    component = pattern.parent if pattern is not None else None
    return component if component is not None and component.kind == 'Component' else None


def component_inputs(pad):
    """A component view changes when either its pad moves or its owner reorders."""
    return (pad, component_of(pad)) if pad is not None else ()


def _members(pad):
    document = pad._owner()
    return document.references.incoming(pad, role='net-member') if document else ()


def get_net(pad):
    links = _members(pad)
    document = pad._owner()
    assignments = document.references.outgoing(pad, role='pad-net') if document else ()
    targets = {link.source.parent.parent for link in links}
    targets.update(link.target for link in assignments)
    if len(links) > 1 or len(assignments) > 1 or len(targets) > 1:
        raise ReferenceError('pad has contradictory net memberships')
    if document and any(issue.message.startswith('pad-net:')
                        for issue in document.references._source_issues(pad)):
        raise ReferenceError('pad has an unresolved net identity')
    return next(iter(targets), None)


def net_number(pad):
    net = get_net(pad)
    return net._ordinal() if net is not None else -1


def net_dependencies(pad):
    return ((pad, 'net-member', 'incoming'), (pad, 'pad-net', 'outgoing'))


def net_ordinal(pad):
    net = get_net(pad)
    return (net,) if net is not None else ()


MEMBER = Record('PcbNetMember', {
    'Pad': Field('Pad', 'reference', getter=member_pad,
                 description='Identity of the placed pad assigned to this net.'),
    'ComponentIndex': Field('ComponentIndex', 'integer',
        getter=lambda member: component_of(member_pad(member))._ordinal(),
        reference_dependencies=lambda member: ((member, 'net-member', 'outgoing'),),
        ordinal_dependencies=lambda member: component_inputs(member_pad(member))),
    'PadIndex': Field('PadIndex', 'integer', getter=lambda member: member_pad(member)._ordinal(),
        reference_dependencies=lambda member: ((member, 'net-member', 'outgoing'),),
        ordinal_dependencies=lambda member: (member_pad(member),)),
}, parameters=('ComponentIndex', 'PadIndex'))


def _placed(document, pad):
    component = component_of(pad)
    if (pad.kind != 'Pad' or pad.parent is None or pad.parent.kind != 'Pads' or
            pad.parent.parent.kind != 'Pattern' or
            component is None or component.parent is not document.one('/Board/Components')):
        raise ReferenceError('net membership requires a placed pad in this PCB')
    if not component['Enabled']:
        raise ReferenceError('net membership requires an enabled component')


def validate_retarget(document, reference, target):
    from .routing import check_pad_net
    if reference.role == 'pad-net':
        _placed(document, reference.source)
        if target.kind != 'Net' or target.parent is not document.one('/Board/Nets'):
            raise ReferenceError('net target is outside this PCB')
        if not target['Enabled']:
            raise ReferenceError('net membership requires an enabled net')
        if _members(reference.source):
            raise ReferenceError('a listed pad already has its assignment through the member')
        if any(link.uid != reference.uid for link in document.references.outgoing(reference.source, role='pad-net')):
            raise ReferenceError('pad already has a net assignment')
        check_pad_net(document, reference.source, target)
        return
    if reference.role != 'net-member':
        return
    source = reference.source
    if (source.schema is not MEMBER or source.parent is None or source.parent.kind != 'Pads' or
            source.parent.parent.kind != 'Net' or
            source.parent.parent.parent is not document.one('/Board/Nets')):
        raise ReferenceError('net member must belong to a net in this PCB')
    if not source.parent.parent['Enabled']:
        raise ReferenceError('net membership requires an enabled net')
    _placed(document, target)
    if document.references.outgoing(target, role='pad-net'):
        raise ReferenceError('pad already has a direct net assignment')
    if any(link.uid != reference.uid for link in _members(target)):
        raise ReferenceError('pad already has a net membership')
    if any(link.uid != reference.uid for link in document.references.outgoing(source, role='net-member')):
        raise ReferenceError('net member already has a pad identity')
    if reference.target is not target:
        check_pad_net(document, reference.target, None)
    check_pad_net(document, target, source.parent.parent)


def validate_removal(document, reference):
    from .routing import check_pad_net
    if reference.role == 'pad-net':
        check_pad_net(document, reference.source, None)
    elif reference.role == 'net-member':
        check_pad_net(document, reference.target, None)


def validate_move(document, node, parent):
    if node.schema is MEMBER:
        if (parent.kind != 'Pads' or parent.parent is None or parent.parent.kind != 'Net' or
                parent.parent.parent is not document.one('/Board/Nets')):
            raise ReferenceError('net member must remain in a net in this PCB')
        if not parent.parent['Enabled']:
            raise ReferenceError('net membership requires an enabled net')
        from .routing import check_pad_net
        check_pad_net(document, member_pad(node), parent.parent)
        document.references._check_collection_changes((node.parent, parent))
    elif node.kind == 'Pad' and get_net(node) is not None:
        pattern = parent.parent
        component = pattern.parent if pattern is not None else None
        if (parent.kind != 'Pads' or pattern is None or pattern.kind != 'Pattern' or
                component is None or component.parent is not document.one('/Board/Components')):
            raise ReferenceError('an assigned pad must remain in a placed component')
        if not component['Enabled']:
            raise ReferenceError('an assigned pad requires an enabled component')


def set_net(pad, target):
    document = pad._owner()
    if document is None:
        raise ReferenceError('attach a pad to a PCB before assigning its net')
    _placed(document, pad)
    if target is not None and (target.kind != 'Net' or target.parent is not document.one('/Board/Nets')):
        raise ReferenceError('net target is outside this PCB')
    if target is not None and not target['Enabled']:
        raise ReferenceError('net membership requires an enabled net')
    current = get_net(pad)
    if current is target:
        return
    from .routing import check_pad_net
    check_pad_net(document, pad, target)
    old = next(iter(_members(pad)), None)
    direct = document.references.outgoing(pad, role='pad-net')
    if direct:
        if target is None:
            document.references.discard(direct[0])
        else:
            document.references.retarget(direct[0], target)
        return
    collection = target.one('Pads') if target is not None else None
    graph = document.references
    graph._check_collection_changes(parent for parent in
        (old.source.parent if old is not None else None, collection) if parent is not None)
    if old is not None:
        if target is None:
            graph.check_removal(old.source, excluding=(old.uid,))
            graph.discard(old)
            old.source.detach()
        else:
            old.source.move_to(collection)
    elif target is not None:
        graph._attach_bound(collection, Element('Item').bind_schema(MEMBER), pad, role='net-member')


def structural_dependents(document, nodes):
    result = {}
    for node in nodes:
        if node.schema is not MEMBER:
            continue
        for link in document.references.outgoing(node, role='net-member'):
            for dependent in (*document.references.incoming(link.target),
                              *document.references.property_consumers(link.target, 'NetNumber')):
                result[dependent.uid] = dependent
    return tuple(result.values())


def validate(document):
    for link in document.references:
        if link.role in ('net-member', 'pad-net'):
            validate_retarget(document, link, link.target)
