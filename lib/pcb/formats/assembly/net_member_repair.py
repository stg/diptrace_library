"""Plan the import repair for routing references to absent components.

Explicit net members remain authored data in ordinary designs. Reconcile them
only when a missing component forces an ordinary trace endpoint to become free.
The plan is checked with the rest of the electrical core before changing input.
"""
from dataclasses import dataclass

from ....common.conversion import import_notice
from ....common.model import Element


@dataclass(frozen=True)
class MemberRepair:
    net: Element
    endpoints: tuple[tuple[Element, str], ...]
    members: tuple[tuple[Element, Element], ...]


def prepare_member_repairs(nets, components, pads):
    """Return affected nets without guessing a target or altering saved records."""
    component_keys = set(components)
    repairs = {}
    for net in nets:
        traces = net.select('Traces/Trace')
        missing = [(trace, end) for trace in traces for end in ('1', '2')
                   if trace['Connected'+end] == 0 and trace['Object'+end] not in component_keys]
        if not missing:
            continue

        endpoints = list(missing)
        missing = set(missing)
        members = []
        seen = set()
        prepared = Element('Pads')
        for trace in traces:
            if not trace.select('Points/Point'):
                continue
            for end in ('1', '2'):
                if trace['Connected'+end] != 0 or (trace, end) in missing:
                    continue
                key = trace['Object'+end], trace['SubObject'+end]
                pad = pads.get(key)
                if pad is None:
                    # Once reconciliation is required, invalid pad selectors
                    # also become free ends. Ambiguous identities still raise.
                    endpoints.append((trace, end))
                elif pad not in seen:
                    seen.add(pad)
                    members.append((prepared.add('Item', *key), pad))
        repairs[net] = MemberRepair(net, tuple(endpoints), tuple(members))
    return repairs


def apply_member_repairs(repairs):
    """Apply preflighted repairs while retaining all trace point geometry."""
    for repair in repairs.values():
        for trace, end in repair.endpoints:
            trace.one('Connected'+end).set_values(-1)
        for row in repair.net.select('Pads/Item'):
            row.detach()
        collection = repair.net.one('Pads')
        for row, pad in repair.members:
            row.move_to(collection)
            pad.one('NetNumber').set_values(repair.net['Number'])
    if repairs:
        import_notice('info', 'missing-component-route-target',
            'Freed routing endpoints to absent components and reconciled the affected net members.',
            tuple(repairs), recoverability='trace geometry and surviving pad connections retained')
