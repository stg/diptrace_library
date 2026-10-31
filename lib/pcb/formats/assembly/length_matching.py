"""Normalize length policies and consume selectors into existing identities."""
from dataclasses import replace

from ....common.conversion import import_notice
from ....common.structural_edits import assembly
from ...model import length_matching as records
from ..errors import PcbError


def _class_results(result, policies):
    """Select the supplied results belonging to current active class rules.

    Class policies are generated in class order; their name and limits come
    from the class. The last supplied result for an active class survives
    normalization. User rule order is independent of that generated view.
    """
    selected, discarded = {}, []
    for policy in policies:
        kind = policy.get('Type', 0)
        if kind not in (0, 1):
            raise PcbError(f'{policy.path}: unknown length-rule type {kind}')
        if kind == 0:
            continue
        if policy.kind == 'MainLengthRule':
            # This is the current working rule, not the class-owned result set.
            continue
        key = policy.get('NetClass', -1)
        target = result.classes.get(key)
        if target is None:
            raise PcbError(f'{policy.path}: unresolved length-rule class {key}')
        if not target.get('CheckLength', False):
            discarded.append(policy)
            continue
        if (previous := selected.get(target)) is not None:
            discarded.append(previous)
        selected[target] = policy
    if discarded:
        import_notice('info', 'obsolete-class-length-results',
                      'Removed superseded or inactive class length results.', discarded,
                      recoverability='current class settings retained')
    return selected, set(discarded)


def assemble_length_rules(result):
    document, core = result.document, result.routing.core
    board = document.one('/Board')
    policies = (*board.children('MainLengthRule'), *board.select('LengthRules/LengthRule'))
    # These dictionaries last only for import. Error snapshots select positions
    # in the supplied policy list, before class ownership and stale-row cleanup.
    positions = {policy: index for index, policy in enumerate(board.select('LengthRules/LengthRule'))}
    source_rows = {(positions[policy], row.values[0]): row
                   for policy in positions for row in policy.select('Rules/Rule')}
    class_results, discarded = _class_results(result, policies)
    owners = {policy: net_class for net_class, policy in class_results.items()}
    consumed, links, clear_values, stale_rows, obsolete_rows = [], [], [], [], []
    for policy in policies:
        if policy in discarded:
            continue
        if policy.kind == 'MainLengthRule' and policy.get('Type', 0) == 1:
            selected = policy.get('NetClass', -1)
            target = result.classes.get(selected)
            if target is None:
                raise PcbError(f'{policy.path}: unresolved main length-rule class {selected}')
            links.append((policy, records.CLASS_ROLE, target))
        consumed.extend(slot for name in ('NetClass', 'Type', 'AnyError')
                        if (slot := policy.child(name)) is not None)
        clear_values.append(policy)
        for row in policy.select('Rules/Rule'):
            endpoints = [tuple(row[name] for name in ('Comp'+str(end), 'Pad'+str(end)))
                         for end in (1, 2)]
            # Nonpositive pad selectors carry no endpoint. Positive selectors
            # must still identify a current pad; obsolete rows are compacted
            # on import rather than made into invented connection targets.
            if any(pad > 0 and (component, pad) not in core.pads for component, pad in endpoints):
                stale_rows.append(row)
                continue
            key = row['NetId']
            net = core.nets.get(key) if key != -1 else None
            if key != -1 and net is None:
                raise PcbError(f'{row.path}: unresolved length connection net {key}')
            if policy in owners and (net is None or net['Class'] is not owners[policy]):
                obsolete_rows.append(row)
                continue
            consumed.append(row.one('NetId'))
            if net is not None:
                links.append((row, records.NET_ROLE, net))
            for end, role in enumerate(records.PAD_ROLES, 1):
                names = 'Comp'+str(end), 'Pad'+str(end)
                selected = tuple(row[name] for name in names)
                consumed.extend(row.one(name) for name in names)
                if selected[1] <= 0:
                    continue
                target = core.pads.get(selected)
                if net is None or target['Net'] is not net:
                    raise PcbError(f'{row.path}: length connection pad contradicts its net')
                links.append((row, role, target))
            clear_values.append(row)
    if stale_rows:
        import_notice('info', 'stale-length-connections',
                      'Removed length connections whose selected pads no longer exist.', stale_rows,
                      recoverability='current policies and valid connections retained')
    if obsolete_rows:
        import_notice('info', 'stale-class-length-connections',
                      'Removed class length results for nets no longer assigned to that class.', obsolete_rows,
                      recoverability='current class assignments and valid results retained')
    with assembly(document):
        for row in (*stale_rows, *obsolete_rows):
            row.detach()
        for slot in consumed:
            slot.detach()
        for node in clear_values:
            node.set_values()
        for policy in discarded:
            policy.detach()
        roots = list(board.children('MainLengthRule')) + list(board.children('LengthRules'))
        scopes = {positions[policy]: policy for policy in positions if policy not in discarded}
        for net_class, policy in class_results.items():
            results = net_class.add('LengthResults')
            for name in ('Rules',):
                if (content := policy.child(name)) is not None:
                    content.move_to(results)
            policy.detach()
            roots.append(results)
            scopes[positions[policy]] = results
        for root in roots:
            for node in root.walk(include_self=True):
                if (schema := records.definition(node)) is not None:
                    node.bind_schema(schema)
        with document.references.binding_batch():
            for source, role, target in links:
                document.references.bind(source, target, role=role, preserve=True)
    return replace(result, length_connections={key: row for key, row in source_rows.items()
                   if row._owner() is document},
                   length_scopes={index: scopes.get(index) for index in positions.values()})
