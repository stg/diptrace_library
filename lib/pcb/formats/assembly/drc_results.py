"""Resolve saved design-check selectors after routing and graphics assembly."""
from ....common.conversion import import_notice
from ....common.references import Guard, Index
from ....common.schema import MISSING
from ....common.structural_edits import assembly
from ...model import drc_results as model
from ..errors import PcbError
from ..result_types import object_type_from_file


# These targets identify an entire object. A saved Point slot is not a
# relationship to one of its authored vertices or another persistent record.
_WHOLE_OBJECT_TYPES = frozenset((*model.PAD_TYPES, *model.HOLE_TYPES,
                                *model.SHAPE_TYPES, 7, 18, 21))


def _at(owner, path, index):
    rows = owner.select(path) if owner is not None else ()
    return rows[index] if 0 <= index < len(rows) else None


def _saved(error, name, default=-1):
    slot = error.child(name)
    if slot is None:
        return default
    if slot.children() or len(slot.values) != 1 or type(slot.values[0]) is not int:
        raise PcbError(f'{slot.path}: expected one integer selector')
    return slot.values[0]


def _object(error, side, graphics):
    core = graphics.rules.routing.core
    mode = _saved(error, 'ObjectType'+side)
    obj, sub, point, ext = (_saved(error, name+side) for name in ('Object', 'SubObject', 'Point', 'ExtObject'))
    if mode < 0:
        return None
    if mode not in model.TARGET_TYPES:
        raise PcbError(f'design-check object domain {mode} mapping is not implemented')
    if mode in (*model.PAUSED_TYPES, *model.PANEL_HOLE_TYPES):
        # Interactive routes and generated panel holes have no saved geometry
        # collection whose members could supply a persistent target identity.
        return None
    if mode != 1 and all(value < 0 for value in (obj, sub, point, ext)):
        return None
    if mode in model.PAD_TYPES:
        return core.pads.get((obj, sub))
    if mode in model.HOLE_TYPES:
        component = core.components.get(obj)
        return graphics.placed_holes.get((component, sub))
    if mode in model.TRACE_TYPES:
        trace = graphics.rules.routing.traces.get((obj, sub))
        return trace if point < 0 else _at(trace, 'Points/Point', point)
    if mode in model.SHAPE_TYPES:
        if ext >= 0:
            return _at(core.document.one('/Board'), 'Components/Component', ext)
        return graphics.drawings.get(obj)
    if mode == 7:
        return graphics.pours.get(obj)
    if mode == 1:
        board = core.document.one('/Board')
        return board if point < 0 else _at(board, 'Points/pt', point)
    if mode == 21:
        return core.teardrops.get((obj, sub))
    if mode == 17:
        pair = _at(core.document.one('/Board'), 'DifferentialPairs/DifferentialPair', obj)
        segment = _at(pair, 'Segments/Segment', sub)
        return _at(segment, 'CenterPoints/CenterPoint', point)
    if mode == 18:
        return graphics.rules.length_connections.get((obj, sub))
    raise PcbError(f'design-check object domain {mode} mapping is not implemented')


def _unresolved(error, side, original, graphics):
    """Resolve available ancestors even when the selected object is unavailable."""
    mode = _saved(error, 'ObjectType'+side)
    obj, sub, point, ext = original
    board, core = graphics.document.one('/Board'), graphics.rules.routing.core
    if mode in (*model.PAUSED_TYPES, *model.PANEL_HOLE_TYPES):
        # These indices do not address any persistent design collection.
        return original, ()
    scopes = []
    if mode in model.TRACE_TYPES or mode == 21:
        net = core.nets.get(obj)
        trace = graphics.rules.routing.traces.get((obj, sub)) if mode != 21 else None
        scopes = [board.child('Nets'), net.child('Traces' if mode != 21 else 'Teardrops') if net is not None else None,
                  trace.child('Points') if trace is not None else None]
        obj = net._ordinal() if net is not None else obj
        sub = trace._ordinal() if trace is not None else sub
    elif mode in model.SHAPE_TYPES and ext >= 0:
        # The qualifier identifies the component. The primitive calculation
        # selector has no corresponding saved footprint drawing identity.
        obj, sub, point = -1, -1, -1
        scopes = [board.child('Components')]
    elif mode == 17:
        pair = _at(board, 'DifferentialPairs/DifferentialPair', obj)
        segment = _at(pair, 'Segments/Segment', sub)
        scopes = [board.child('DifferentialPairs'), pair.child('Segments') if pair is not None else None,
                  segment.child('CenterPoints') if segment is not None else None]
    elif mode == 18:
        policy = graphics.rules.length_scopes.get(obj)
        scopes = [board.child('NetClasses'), board.child('LengthRules'),
                  policy.child('Rules') if policy is not None else None]
    else:
        scopes = [board.child('CopperPours' if mode == 7 else 'Shapes' if mode in model.SHAPE_TYPES else 'Points')]
    return (obj, sub, point, ext), tuple(scope for scope in scopes if scope is not None) or (board,)


def assemble_results(graphics):
    """Consume saved error IDs and layer masks into current result relationships."""
    document, board = graphics.document, graphics.document.one('/Board')
    collection = board.child('DesignErrors')
    if collection is None:
        with assembly(document):
            collection = board.add('DesignErrors').bind_schema(model.ERRORS)
        return graphics
    if collection.arguments:
        raise PcbError('unexpected design-error collection arguments')
    plans, inactive, repaired, unavailable_rows, drawing_details, paused_rows, panel_rows = [], [], [], [], [], [], []
    unused_points = []
    for error in collection.children():
        if error.kind != 'DesignError':
            raise PcbError(f'{error.path}: expected a design-check result')
        if not error.get('Enabled', True):
            inactive.append(error)
            continue
        targets = []
        for side, role in zip(('1', '2'), model.OBJECT_ROLES):
            saved = _saved(error, 'ObjectType'+side)
            if (current := object_type_from_file(saved)) != saved:
                error.one('ObjectType'+side).set_values(current)
            target = _object(error, side, graphics)
            original = tuple(_saved(error, name+side) for name in ('Object', 'SubObject', 'Point', 'ExtObject'))
            if current in _WHOLE_OBJECT_TYPES:
                if original[2] >= 0:
                    unused_points.append(error)
                original = (*original[:2], -1, original[3])
            targets.append((side, role, target, original))
        mask = error.child('Lays')
        flags = []
        if mask is not None:
            if mask.arguments:
                raise PcbError(f'{mask.path}: unexpected layer-mask arguments')
            for index, flag in enumerate(mask.children()):
                if flag.kind != 'Item' or flag.children() or len(flag.values) != 1 or type(flag.values[0]) is not bool:
                    raise PcbError(f'{flag.path}: expected a layer flag')
                if flag.values[0]:
                    flags.append(index)
        plans.append((error, targets, flags, mask, {name: _saved(error, name) for name in ('RuleLay', 'ObjectNetClass1', 'ObjectNetClass2')}))
    with assembly(document), document.references.binding_batch():
        collection.bind_schema(model.ERRORS)
        for error in inactive:
            error.detach()
        for error, targets, flags, mask, selectors in plans:
            for name in ('RuleLay', 'ObjectNetClass1', 'ObjectNetClass2',
                         *(name+side for side in ('1', '2') for name in ('Object', 'SubObject', 'Point', 'ExtObject'))):
                if (slot := error.child(name)) is not None:
                    slot.detach()
            error.set_values()
            error.bind_schema(model.ERROR)
            for name, field in model.ERROR.fields.items():
                if field.getter is None and field.default is not MISSING and error.child(name) is None:
                    error.add(name, field.default)
            if mask is not None:
                mask.detach()
            layers = error.add('Layers').bind_schema(model.LAYERS)
            for index in flags:
                row = layers.add('Layer').bind_schema(model.LAYER)
                target = graphics.rules.layers.get(index)
                if target is None:
                    missing = row.add('UnresolvedIndex', index)
                    unavailable_rows.append(row)
                    document.references.note(row, 'drc-layer: copper layer cannot be resolved',
                        Index(missing), collections=(board.one('Layers'),))
                else:
                    document.references.bind(row, target, role='drc-layer', preserve=True)
            for side, role, target, original in targets:
                mode = error['ObjectType'+side]
                if mode in model.SHAPE_TYPES and original[3] >= 0 and any(value >= 0 for value in original[:3]):
                    drawing_details.append(error)
                known_teardrop_scope = (mode == 21 and (net := graphics.rules.routing.core.nets.get(original[0])) is not None
                                        and net.child('Teardrops') is not None)
                if target is None and (mode in (*model.PAD_TYPES, *model.HOLE_TYPES) or known_teardrop_scope):
                    if any(value >= 0 for value in original[:3]):
                        repaired.append(error)
                    continue
                if mode < 0 or mode != 1 and all(value < 0 for value in original):
                    continue
                if target is None:
                    values, scopes = _unresolved(error, side, original, graphics)
                    unavailable = error.add('UnresolvedTarget'+side, *values).bind_schema(model.UNRESOLVED)
                    expected = mode in (*model.PAUSED_TYPES, *model.PANEL_HOLE_TYPES)
                    (paused_rows if mode in model.PAUSED_TYPES else
                     panel_rows if mode in model.PANEL_HOLE_TYPES else unavailable_rows).append(error)
                    document.references.note(error, role+': object cannot be resolved',
                        *(Index(unavailable, i) for i in range(4)), collections=scopes,
                        guards=(Guard(error.one('ObjectType'+side), (mode,)),),
                        severity='info' if expected else 'warning')
                else:
                    document.references.bind(error, target, role=role, preserve=True)
            for name, role, choices in (
                    ('RuleLay', 'drc-rule-layer', graphics.rules.layers),
                    ('ObjectNetClass1', 'drc-class-1', graphics.rules.classes),
                    ('ObjectNetClass2', 'drc-class-2', graphics.rules.classes)):
                index = selectors[name]
                if index < 0:
                    continue
                target = choices.get(index)
                if target is None:
                    slot = error.add('Unresolved'+name, index)
                    unavailable_rows.append(error)
                    document.references.note(error, role+': selector cannot be resolved', Index(slot),
                        collections=(board.one('Layers' if name == 'RuleLay' else 'NetClasses'),))
                else:
                    document.references.bind(error, target, role=role, preserve=True)
    if repaired:
        import_notice('info', 'stale-design-error-targets',
            'Detached unavailable objects from supplied design-check results.', repaired,
            recoverability='result location and measured values retained')
    if unavailable_rows:
        import_notice('warning', 'unresolved-design-error-targets',
            'Supplied design-check results contain unavailable object, class or layer selections.',
            unavailable_rows, recoverability='unresolved selections remain explicit and can be repaired or cleared')
    if drawing_details:
        import_notice('info', 'design-error-drawing-detail',
            'Kept component drawing-check selections without unavailable calculation primitive indices.',
            tuple(dict.fromkeys(drawing_details)),
            recoverability='component identity and supplied result location, value and threshold retained')
    if unused_points:
        import_notice('info', 'unused-design-error-point',
            'Consumed unused point selectors on whole-object design-check targets.',
            tuple(dict.fromkeys(unused_points)),
            recoverability='object identity and supplied result location, value and threshold retained')
    if paused_rows:
        import_notice('info', 'paused-design-error-targets',
            'Saved check results refer to interactive routing geometry absent from the design.',
            tuple(dict.fromkeys(paused_rows)),
            recoverability='supplied measurements and unresolved selectors remain editable; no route is invented')
    if panel_rows:
        import_notice('info', 'generated-panel-hole-targets',
            'Saved check results refer to panel holes generated from the panel settings.',
            tuple(dict.fromkeys(panel_rows)),
            recoverability='selectors and measurements remain; individual hole geometry is not stored')
    return graphics
