"""Ordered net members own pin membership; numeric occurrences are calculated.

Incomplete or contradictory imported links remain unresolved compatibility
data. Only an agreed relationship is consolidated; no missing target is guessed.
"""
from ...common.model import Element
from ...common.references import ReferenceError
from ...common.schema import Field, Record


def _net(member):
    return member.parent.parent


def _member_reference(member):
    document = member._owner()
    references = document.references.outgoing(member, role='net-member') if document else ()
    if len(references) != 1:
        raise ReferenceError('net member does not have one resolved pin')
    return references[0]


def member_pin(member):
    return _member_reference(member).target


def _members(pin):
    document = pin._owner()
    return document.references.incoming(pin, role='net-member') if document else []


def get_net(pin):
    members = _members(pin)
    document = pin._owner()
    assignments = document.references.outgoing(pin, role='pin-net') if document else ()
    targets = {_net(reference.source) for reference in members}
    targets.update(reference.target for reference in assignments)
    if len(members) > 1 or len(targets) > 1:
        raise ReferenceError('pin has contradictory net memberships')
    if document and any(issue.source is pin and issue.message.startswith('pin-net:')
                        for issue in document.references.issues):
        raise ReferenceError('pin has an unresolved net identity')
    return next(iter(targets), None)


def net_number(pin):
    field = pin.child('NetNumber')
    if field is not None and field.schema is not NET_NUMBER:
        return field.values[0]
    target = get_net(pin)
    return target._ordinal() if target is not None else -1


def _pin_number(field):
    return net_number(field.parent) if field.parent is not None else -1


def net_dependencies(pin):
    field = pin.child('NetNumber')
    if field is not None and field.schema is not NET_NUMBER:
        return ()
    return ((pin, 'net-member', 'incoming'), (pin, 'pin-net', 'outgoing'))


def net_ordinal(pin):
    if not net_dependencies(pin):
        return ()
    target = get_net(pin)
    return (target,) if target is not None else ()


NET_NUMBER = Record('NetNumber', {
    'Value': Field('Value', 'integer', getter=_pin_number,
                    reference_dependencies=lambda field: net_dependencies(field.parent),
                    ordinal_dependencies=lambda field: net_ordinal(field.parent)),
}, parameters=('Value',), description='Calculated compatibility view of a pin net.')

MEMBER = Record('NetMember', {
    'Pin': Field('Pin', 'reference', getter=member_pin, description='The member pin identity.'),
    'PartIndex': Field('PartIndex', 'integer', getter=lambda row: member_pin(row).parent.parent._ordinal(),
                       reference_dependencies=lambda row: ((row, 'net-member', 'outgoing'),),
                       ordinal_dependencies=lambda row: (member_pin(row).parent.parent,)),
    'PinIndex': Field('PinIndex', 'integer', getter=lambda row: member_pin(row)._ordinal(),
                      reference_dependencies=lambda row: ((row, 'net-member', 'outgoing'),),
                      ordinal_dependencies=lambda row: (member_pin(row),)),
}, parameters=('PartIndex', 'PinIndex'), description='An ordered pin membership in its containing net.')


def _calculated_number(pin):
    field = pin.child('NetNumber')
    if field is None:
        field = pin.add('NetNumber')
    field.bind_schema(NET_NUMBER)


def establish_member(member):
    """Replace resolved numeric occurrences with the single pin identity view."""
    if member.schema is not None:
        for name in member.schema.parameters:
            field = member.child(name)
            if field is not None:
                field.detach()
        member._schema = None
    member.set_values()
    member.bind_schema(MEMBER)


def consolidate(document):
    """Consume agreeing imported occurrences into one identity relationship."""
    if document.representation != 'schematic':
        return
    graph = document.references
    assignments = {}
    members = {}
    for reference in graph:
        if reference.role == 'pin-net':
            assignments.setdefault(reference.source, []).append(reference)
        elif reference.role == 'net-member':
            members.setdefault(reference.target, []).append(reference)
    unknown = {issue.source for issue in graph.issues if issue.message.startswith('pin-net:')}
    for pin in document.select('/Schematic/Components/Part/Pins/Pin'):
        links = members.get(pin, ())
        own = assignments.get(pin, ())
        if len(links) == len(own) == 1 and _net(links[0].source) is own[0].target:
            member = links[0].source
            graph.discard(links[0])
            graph.discard(own[0])
            # The two adapter numbers cease to be stored facts. Their current
            # values are supplied by the same identity link in every adapter.
            establish_member(member)
            graph.bind(member, pin, role='net-member', preserve=True)
            _calculated_number(pin)
        elif not links and not own and pin not in unknown and net_number(pin) < 0:
            _calculated_number(pin)


def _placed(pin, document):
    if (not isinstance(pin, Element) or pin.kind != 'Pin' or pin.parent is None or
            pin.parent.kind != 'Pins' or pin.parent.parent is None or
            pin.parent.parent.parent is not document.one('/Schematic/Components')):
        raise ReferenceError('net membership requires a placed pin in this schematic')


def _check_wires(document, pin, target):
    for reference in document.references.incoming(pin):
        if reference.role.startswith('wire-pin-') and _net(reference.source) is not target:
            raise ReferenceError('net change would contradict an attached wire; edit the connection first')


def validate_retarget(document, reference, target):
    if reference.role != 'net-member' or reference.indices:
        return
    if reference.source.schema is not MEMBER:
        raise ReferenceError('identity membership requires a canonical net member')
    if any(item.uid != reference.uid for item in document.references.outgoing(reference.source, role='net-member')):
        raise ReferenceError('net member already has a pin identity')
    _placed(target, document)
    net = _net(reference.source)
    if net.parent is not document.one('/Schematic/Nets'):
        raise ReferenceError('net member is outside this schematic')
    other = [item for item in _members(target) if item.uid != reference.uid]
    if other or document.references.outgoing(target, role='pin-net'):
        raise ReferenceError('pin already has a net membership')
    get_net(target)  # Refuse an unresolved identity before changing either side.
    if reference.target is not target:
        _check_wires(document, reference.target, None)
    _check_wires(document, target, net)


def validate_move(document, member, parent):
    if member.schema is not MEMBER:
        return
    if (parent.kind != 'Parts' or parent.parent is None or parent.parent.kind != 'Net' or
            parent.parent.parent is not document.one('/Schematic/Nets')):
        raise ReferenceError('net member must remain in a net in this schematic')
    document.references._check_collection_changes((member.parent, parent))
    _check_wires(document, member_pin(member), parent.parent)


def validate_removal(document, reference):
    if reference.role == 'net-member' and not reference.indices:
        _check_wires(document, reference.target, None)


def set_net(pin, target):
    document = pin._owner()
    if document is None:
        raise ReferenceError('attach a pin to a schematic before assigning its net')
    _placed(pin, document)
    if target is not None and (target.kind != 'Net' or target.parent is not document.one('/Schematic/Nets')):
        raise ReferenceError('net target is outside this schematic')
    current = get_net(pin)
    links = _members(pin)
    if (any(link.indices for link in links) or
            document.references.outgoing(pin, role='pin-net')):
        raise ReferenceError('inconsistent imported membership must be resolved before editing')
    if current is target:
        return
    _check_wires(document, pin, target)
    old = links[0].source if links else None
    parts = target.child('Parts') if target is not None else None
    if target is not None and parts is None:
        raise ReferenceError('net is missing its member collection')
    graph = document.references
    graph._check_collection_changes(parent for parent in
                                     (old.parent if old is not None else None, parts) if parent is not None)
    if old is not None:
        if target is None:
            graph.check_removal(old, excluding=(links[0].uid,))
            graph.discard(links[0])
            old.detach()
        else:
            old.move_to(parts)
    elif target is not None:
        member = Element('pt').bind_schema(MEMBER)
        graph._attach_bound(parts, member, pin, role='net-member')
    _calculated_number(pin)
