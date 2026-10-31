"""Consume ratline component/pad keys without recalculating supplied geometry."""
from ....common.conversion import import_notice
from ....common.structural_edits import assembly
from ...model import ratlines as model
from ..errors import PcbError


def assemble_ratlines(core):
    document = core.document
    board = document.one('/Board')
    if board.child('Ratlines') is not None:
        raise PcbError('duplicate ratline input representations')
    collection = board.child('Connections')
    if collection is None:
        with assembly(document):
            board.add('Ratlines').bind_schema(model.RATLINES)
        return core
    if collection.values or any(row.kind != 'Connection' for row in collection.children()):
        raise PcbError('expected named ratline input records')
    current, inactive, stale, consumed, links = [], [], [], [], []
    for row in collection.children('Connection'):
        if not row.get('Enabled', True):
            inactive.append(row)
            continue
        endpoints = [tuple(row[name] for name in ('Comp'+str(end), 'Pad'+str(end))) for end in (1, 2)]
        if any(pad > 0 and (component, pad) not in core.pads for component, pad in endpoints):
            stale.append(row)
            continue
        for end, (role, (component, pad)) in enumerate(zip(model.ROLES, endpoints), 1):
            consumed.extend(row.one(name+str(end)) for name in ('Comp', 'Pad'))
            if pad > 0:
                links.append((row, role, core.pads[component, pad]))
        current.append(row)
    if stale:
        import_notice('info', 'stale-ratlines', 'Removed ratlines whose selected pads no longer exist.', stale,
                      recoverability='current electrical data and valid ratlines retained')
    with assembly(document):
        collection.kind = 'Ratlines'
        collection.bind_schema(model.RATLINES)
        for row in (*inactive, *stale):
            row.detach()
        for slot in consumed:
            slot.detach()
        for row in current:
            row.kind = 'Ratline'
            row.set_values()
            row.bind_schema(model.RATLINE)
        with document.references.binding_batch():
            for source, role, target in links:
                document.references.bind(source, target, role=role, preserve=True)
    return core
