"""Consume group caches into current connectivity and one policy per group."""
from ....common.model import Element
from ....common.structural_edits import assembly
from ...model import connection_policies as model
from ...model.connection_groups import groups
from ..errors import PcbError


def assemble_groups(core, *, default_connect_all=False):
    model.POLICY.fields['ConnectAll'].validate(default_connect_all)
    prepared = []
    for component in core.components.records:
        collection = component.child('InternalConnections')
        saved = collection.children('IntCon') if collection is not None else ()
        topology = groups(component)
        group_numbers = {frozenset(group): index for index, group in enumerate(topology)}
        flags = {}
        for record in saved:
            keys = [item.values[0] for item in record.select('PadId/Item')]
            if not keys:
                continue
            targets = [core.component_pads[component].get(key) for key in keys]
            if any(target is None for target in targets):
                raise PcbError('unresolved pad in saved internal connection group')
            number = group_numbers.get(frozenset(targets))
            if number is None:
                raise PcbError('saved internal connection group disagrees with pad labels and definitions')
            flag = record['ConnectAll']
            if number in flags and flags[number] != flag:
                raise PcbError('saved internal connection group has contradictory policies')
            flags[number] = flag
        prepared.append((component, collection, tuple(
            (group[0], flags.get(index, default_connect_all))
            for index, group in enumerate(topology))))
    with assembly(core.document):
        links = []
        for component, previous, policies in prepared:
            if previous is not None:
                previous.detach()
            collection = component.add('InternalConnections').bind_schema(model.POLICIES)
            for pad, flag in policies:
                policy = Element('IntCon')
                policy.add('ConnectAll', flag)
                collection.append(policy.bind_schema(model.POLICY))
                links.append((policy, pad))
        with core.document.references.binding_batch():
            for policy, pad in links:
                core.document.references.bind(policy, pad, role=model.ROLE, preserve=True)
    return core
