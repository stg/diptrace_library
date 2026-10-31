"""Modernize calculated paired-pad rows before importing routing identities."""
from ....common.conversion import import_notice
from ....common.geometry import transform_point
from ....common.model import Element
from ....common.structural_edits import assembly
from ...model.pair_routing import PEER, SEGMENT_TRACES
from ..errors import PcbError
from .pair_matching import PadLocation, infer_members


def _members(pair, pads):
    result = []
    for row in pair.select('PadPoints/PadPoint'):
        result.append(tuple(pads.get((row.one(side+'Comp').values[0],
                                      row.one(side+'Pad').values[0])) for side in ('Pos', 'Neg')))
    return tuple(result)


def _limit(board, pair):
    classes = board.select('NetClasses/NetClass')
    index = pair.get('NetClass', -1)
    if not 0 <= index < len(classes):
        raise PcbError(f'unresolved differential-pair net class {index}')
    net_class = classes[index]
    rows = net_class.select('LayProperties/LayProperty')
    settings = board.child('Settings')
    routing = settings.child('Routing') if settings is not None else None
    default_rows = classes[0].select('LayProperties/LayProperty') if classes else ()

    def fallback(name, field):
        slot = routing.child(name) if routing is not None else None
        value = slot.values[0] if slot is not None else default_rows[0].get(field, 0) if default_rows else 0
        return 0 if value is None else float(value)

    def current(field, default):
        value = float(rows[0].get(field, -1)) if rows else -1
        return value if value > 0 else default

    width = current('Width', fallback('TraceWidth', 'Width'))
    gap = current('DifClearance', fallback('TraceClearance', 'Clearance'))
    return max(2*float(net_class.get('MaxUncoupledLength', 0)), 20*(width+gap))


def refresh_members(decoded, core, traces, pairs, segment_links, peer_links):
    """Return inferred row targets, leaving ordinary identity binding to callers.

    Input selectors are temporary. Regeneration keeps matching row identities
    and updates existing segment selectors before their normal binding pass.
    """
    if not getattr(decoded, 'requires_pair_refresh', False) and not any(
            not pair.select('PadPoints/PadPoint') for pair in pairs):
        return {}
    board = decoded.board
    previous = {pair: _members(pair, core.pads) for pair in pairs}
    tagged = {pad for rows in previous.values() for row in rows for pad in row if pad is not None}
    segment_traces = {target for _, role, target in segment_links if role in SEGMENT_TRACES}
    peer_traces = {target for _, role, target in peer_links if role == PEER}
    attached = set()
    for trace in traces.values():
        if trace in peer_traces and trace not in segment_traces:
            continue
        for end in (1, 2):
            if trace['Connected'+str(end)] == 0:
                pad = core.pads.get((trace['Object'+str(end)], trace['SubObject'+str(end)]))
                if pad in tagged:
                    attached.add(pad)
    by_net, locations = {}, {}
    for component in board.select('Components/Component'):
        if not component['Enabled']:
            continue
        for pad in component.select('Pattern/Pads/Pad'):
            if pad['Net'] is not None:
                by_net.setdefault(pad['Net'], []).append((component, pad))

    def location(item):
        component, pad = item
        if pad not in locations:
            x, y = transform_point((pad['X'], pad['Y']), origin=(component['X'], component['Y']),
                                   angle=component['Angle'])
            locations[pad] = PadLocation(pad, x, y, surface=pad['SurfacePad'],
                side=bool(component.get('BottomSide', False)) ^ bool(pad['Sided']),
                static_via=component.one('Pattern')['Type'] == 16)
        return locations[pad]
    plans = []
    for pair in pairs:
        positive_net, negative_net = (core.nets.get(pair[side+'Net']) for side in ('Pos', 'Neg'))
        if positive_net is None or negative_net is None:
            raise PcbError('unresolved saved differential-pair net')
        valid = all(first is not None and second is not None
                    and first['Net'] is positive_net and second['Net'] is negative_net
                    for first, second in previous[pair])
        automatic = pair.get('AutoPadPoints', True)
        if not automatic and valid:
            continue
        positive, negative = by_net.get(positive_net, ()), by_net.get(negative_net, ())
        chosen = infer_members(map(location, positive), map(location, negative), previous=previous[pair],
                               attached=attached, limit=_limit(board, pair)) if positive and negative else ()
        old_rows = tuple(pair.select('PadPoints/PadPoint'))
        reusable = {}
        for row, targets in zip(old_rows, previous[pair]):
            reusable.setdefault(frozenset(targets), []).append(row)
        rows = []
        for targets in chosen:
            available = reusable.get(frozenset(targets), [])
            rows.append((available.pop(0) if available else Element('PadPoint'), targets))
        new_positions = {frozenset(targets): index for index, (_, targets) in enumerate(rows)}
        selectors = []
        for segment in pair.select('Segments/Segment'):
            for end in ('Start', 'End'):
                field = segment.child(end+'Point')
                index = field.values[0] if field is not None else -1
                if segment.get(end+'Segment', -1) < 0 and 0 <= index < len(old_rows):
                    selectors.append((field, new_positions.get(frozenset(previous[pair][index]), -1)))
        changed = not automatic or tuple(targets for _, targets in rows) != previous[pair]
        plans.append((pair, rows, selectors, changed))
    inferred = {}
    with assembly(core.document):
        for pair, rows, selectors, changed in plans:
            collection = pair.child('PadPoints')
            if collection is None:
                collection = pair.add('PadPoints')
            retained = {row for row, _ in rows}
            for row in tuple(collection.children('PadPoint')):
                if row not in retained:
                    row.detach()
            for index, (row, targets) in enumerate(rows):
                if row.parent is None:
                    collection.append(row)
                if row._ordinal() != index:
                    row.move_to(collection, index)
                inferred[row] = targets
            for field, index in selectors:
                field.set_values(index)
            if not pair.get('AutoPadPoints', True):
                pair.one('AutoPadPoints').set_values(True)
            if changed:
                import_notice('info', 'automatic-pair-members',
                    'Regenerated automatic differential-pair members and their endpoint references.', (pair,),
                    recoverability='calculated membership follows the current pads, routing and class rules')
    return inferred
