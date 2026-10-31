"""Modernize and bind dimension selectors to current PCB identities."""
from dataclasses import dataclass
from collections.abc import Mapping

from ....common.dimension_refs import local_attachment
from ....common.references import Guard, Index
from ....common.conversion import import_notice
from ...model.dimensions import LOCAL_ROLES, BOARD_ROLES, BOARD_VERTEX_TYPES
from .source_index import SourceIndex


@dataclass(frozen=True)
class BoardDimensionScope:
    """Temporary saved-key maps, independent of current collection positions."""
    patterns: Mapping
    nets: dict
    traces: dict
    pours: dict
    drawings: dict


def board_dimension_scope(routing, footprints, *, drawings, pours):
    core = routing.core
    owned = {footprint.pattern.parent: footprint for footprint in footprints}
    patterns = SourceIndex(((key, owned[component]) for key, component in core.components.entries),
                           'dimension component')
    return BoardDimensionScope(patterns, core.nets, routing.traces, pours, drawings)


def _at(records, number):
    return records[number] if 0 <= number < len(records) else None


def _drawing_points(shape):
    points = shape.child('Points_New')
    return points if points is not None else shape.child('Points')


def _bind(document, dimension, role, attachment, scopes):
    target, indices, guards = attachment
    if target is None:
        document.references.note(dimension, f'{role}: target index cannot be resolved', *indices,
            collections=scopes, guards=guards)
        return
    # Saved selectors are consumed at the import boundary. Current order then
    # belongs to the graph, using each field's documented number offset.
    for item in indices:
        ancestor = target
        for _ in range(item.ancestor):
            ancestor = ancestor.parent
        item.field.set_values(ancestor._ordinal()+item.offset)
    document.references.bind(dimension, target, *indices, role=role, guards=guards, preserve=True)


def _scopes(footprint, dimension, side):
    mode = dimension['Connected'+side]
    pattern = footprint.pattern
    collection = pattern.child({0: 'Pads', 1: 'Shapes', 2: 'Holes', 3: 'Pads'}.get(mode, ''))
    scopes = [collection] if collection is not None else []
    if mode == 1:
        shape = footprint.shapes.get(dimension['SubObject'+side])
        if shape is not None and (points := shape.child('Points_New')) is not None:
            scopes.append(points)
    elif mode == 3:
        pad = footprint.pads.get(dimension['Object'+side])
        if pad is not None:
            scopes.append(pad)
            scopes.extend(points for terminal in pad.children('PadTerminal')
                          if (points := terminal.child('ShapePoints')) is not None)
    return tuple(scopes)


def _detach_unavailable(dimension, side, domain):
    radius = dimension.get('Type', 0) == 3
    import_notice('info', 'dimension-attachment-normalization',
        'Removed an invalid radius dimension.' if radius else
        f'Detached unavailable {domain} dimension endpoint {side}, retaining its coordinates.',
        (dimension,), recoverability='usable current design data retained')
    if radius:
        dimension.detach()
        return
    dimension.one('Connected'+side).set_values(-1)
    for name in ('Object', 'SubObject', 'Point'):
        if (field := dimension.child(name+side)) is not None:
            field.set_values(0)


def prepare_local_dimensions(footprint):
    """Modernize invalid local attachments before registering relationships."""
    objects = {0: footprint.pads, 1: footprint.shapes, 2: footprint.holes}
    for dimension in footprint.pattern.select('Dimensions/Dimension'):
        if not dimension.get('Enabled', True):
            continue
        for side in ('1', '2'):
            mode = dimension.get('Connected'+side, -1)
            if mode not in (0, 1, 2, 3):
                continue
            attachment = local_attachment(dimension, side, objects)
            if attachment is None or attachment[0] is not None:
                continue
            _detach_unavailable(dimension, side, 'local')
            if dimension.parent is None:
                break


def prepare_board_dimensions(document, scope):
    """Apply established loading repairs before board groups are bound.

    Eligibility differs from target resolution: a valid drawing can still have
    an unavailable vertex. Such an unresolved vertex is not a reason to invent
    a disconnection rule that the board loader does not apply.
    """
    board = document.one('/Board')
    patterns = scope.patterns
    outline = board.child('Points')
    outline_count = len(outline.children('pt')) if outline is not None else 0
    for dimension in board.select('Dimensions/Dimension'):
        if not dimension.get('Enabled', True):
            continue
        for side in ('1', '2'):
            mode = dimension.get('Connected'+side, -1)
            if mode in (0, 1, 2, 7):
                footprint = patterns.get(dimension['Object'+side])
                valid = footprint is not None and footprint.pattern.parent['Enabled']
                if valid and mode != 7:
                    objects = {0: footprint.pads, 1: footprint.shapes, 2: footprint.holes}[mode]
                    target = objects.get(dimension['SubObject'+side])
                    valid = target is not None
                    if valid and mode == 0 and dimension['Point'+side] >= 10:
                        vertices = target.select('PadPoints_New/pt')
                        valid = target['PadShape_New'] == 3 and dimension['Point'+side]-10 < len(vertices)
            elif mode == 6:
                valid = board.get('Enabled', True) and 0 <= dimension['Point'+side] < outline_count
            elif mode == 3:
                net = scope.nets.get(dimension['Object'+side])
                trace = scope.traces.get((dimension['Object'+side], dimension['SubObject'+side]))
                points = trace.select('Points/Point') if trace is not None else ()
                number = dimension['Point'+side]
                valid = net is not None and net['Enabled'] and 0 <= number < len(points)
                if valid and dimension.get('Type', 0) == 3:
                    valid = 0 < number < len(points)-1
            elif mode == 4:
                pour = scope.pours.get(dimension['Object'+side])
                points = pour.select('Points/pt') if pour is not None else ()
                valid = 0 <= dimension['Point'+side] < len(points)
            elif mode == 5:
                valid = dimension['Object'+side] in scope.drawings
            else:
                continue
            if not valid:
                _detach_unavailable(dimension, side, 'board')
                if dimension.parent is None:
                    break


def bind_local_dimensions(document, footprint):
    objects = {0: footprint.pads, 1: footprint.shapes, 2: footprint.holes}
    for dimension in footprint.pattern.select('Dimensions/Dimension'):
        for side, role in zip(('1', '2'), LOCAL_ROLES):
            attachment = local_attachment(dimension, side, objects, offset=1)
            if attachment is None:
                continue
            _bind(document, dimension, role, attachment, _scopes(footprint, dimension, side))


def bind_board_dimensions(document, scope):
    """Bind board attachments whose target domains have been established.

    Object and trace selectors use saved keys. Footprint-local pad, drawing and
    hole positions require their own boundary import maps.
    Board drawing corner codes remain literal; true vertices bind their points.
    """
    board = document.one('/Board')
    components = board.one('Components')
    patterns = scope.patterns
    outline = board.child('Points')
    outline_points = outline.children('pt') if outline is not None else ()
    for dimension in board.select('Dimensions/Dimension'):
        for side, role in zip(('1', '2'), BOARD_ROLES):
            mode = dimension.get('Connected'+side, -1)
            if mode < 0 or mode == 8:
                # Panel anchors refer to board-wide panel settings rather than
                # an array member. Component origins have their own identity.
                continue
            guard = (Guard(dimension.one('Connected'+side), (mode,)),)
            if mode == 7:
                footprint = patterns.get(dimension['Object'+side])
                target = footprint.pattern.parent if footprint is not None else None
                attachment = target, (Index(dimension.one('Object'+side)),), guard
                _bind(document, dimension, role, attachment, (components,))
            elif mode == 6:
                number = dimension['Point'+side]
                target = outline_points[number] if 0 <= number < len(outline_points) else None
                attachment = target, (Index(dimension.one('Point'+side)),), guard
                _bind(document, dimension, role, attachment, (outline,) if outline is not None else (board,))
            elif mode in (0, 1, 2):
                footprint = patterns.get(dimension['Object'+side])
                owner = dimension.one('Object'+side)
                if footprint is None:
                    attachment = None, (Index(owner), Index(dimension.one('SubObject'+side))), guard
                    _bind(document, dimension, role, attachment, (components,))
                    continue
                objects = {0: footprint.pads, 1: footprint.shapes, 2: footprint.holes}
                target, indices, guards = local_attachment(dimension, side, objects, offset=1 if mode == 0 else 0)
                ancestor = 5 if target is not None and target.kind == 'pt' else 3
                scopes = (components, *_scopes(footprint, dimension, side))
                if mode == 0 and target is not None and dimension['Point'+side] >= 10:
                    pad = target
                    points = pad.child('PadPoints_New')
                    vertices = points.children('pt') if points is not None else ()
                    number = dimension['Point'+side]-10
                    target = vertices[number] if pad['PadShape_New'] == 3 and 0 <= number < len(vertices) else None
                    indices = (Index(dimension.one('SubObject'+side), ancestor=2, offset=1),
                               Index(dimension.one('Point'+side), offset=10))
                    ancestor = 5
                    if points is not None:
                        scopes = (*scopes, points)
                attachment = target, (Index(owner, ancestor=ancestor), *indices), guards
                _bind(document, dimension, role, attachment, scopes)
            elif mode == 3:
                net = scope.nets.get(dimension['Object'+side])
                trace = scope.traces.get((dimension['Object'+side], dimension['SubObject'+side]))
                points = trace.select('Points/Point') if trace is not None else ()
                target = _at(points, dimension['Point'+side])
                indices = (Index(dimension.one('Object'+side), ancestor=4),
                           Index(dimension.one('SubObject'+side), ancestor=2), Index(dimension.one('Point'+side)))
                collections = [board.one('Nets')]
                if net is not None:
                    collections.append(net.one('Traces'))
                if trace is not None:
                    collections.append(trace.one('Points'))
                _bind(document, dimension, role, (target, indices, guard), tuple(collections))
            elif mode == 4:
                pour = scope.pours.get(dimension['Object'+side])
                points = pour.select('Points/pt') if pour is not None else ()
                target = _at(points, dimension['Point'+side])
                indices = (Index(dimension.one('Object'+side), ancestor=2), Index(dimension.one('Point'+side)))
                collections = (board.one('CopperPours'), pour.one('Points')) if pour is not None else (board.one('CopperPours'),)
                _bind(document, dimension, role, (target, indices, guard), collections)
            elif mode == 5:
                shape = scope.drawings.get(dimension['Object'+side])
                vertices = shape is not None and shape['Type'] in BOARD_VERTEX_TYPES
                points = _drawing_points(shape) if shape is not None else None
                target = (_at(points.children('pt'), dimension['Point'+side]) if points is not None else None) if vertices else shape
                indices = ((Index(dimension.one('Object'+side), ancestor=2), Index(dimension.one('Point'+side)))
                           if vertices else (Index(dimension.one('Object'+side)),))
                collections = (board.one('Shapes'), points) if vertices and points is not None else (board.one('Shapes'),)
                _bind(document, dimension, role, (target, indices, guard), collections)
            else:
                collection = board.child({3: 'Nets', 4: 'CopperPours', 5: 'Shapes'}.get(mode, ''))
                scopes = (collection,) if collection is not None else (board,)
                fields = tuple(Index(dimension.one(name+side)) for name in ('Object', 'SubObject', 'Point'))
                document.references.note(dimension, f'{role}: attachment mode {mode} is not implemented',
                    *fields, collections=scopes, guards=guard)
