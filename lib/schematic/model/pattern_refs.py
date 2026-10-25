"""Local footprint pad assignments and dimension attachments."""
from .traversal import (footprints, symbols)
from ...common.references import (Guard, Index)
from ...common.dimension_refs import local_attachment
from .refs import (_at, _integer, _children)
from .local_keys import (missing_key)
from .reference_scope import select as source_records


LOCAL_OBJECTS = (('Pads', 'Pad'), ('Shapes', 'Shape'), ('Holes', 'Hole'))


def _real_member(records, number):
    return _at(records, number) if number is not None and 1 <= number < len(records)-1 else None


def _dimension_link(dimension, side, objects):
    mode = dimension.child('Connected'+side)
    member = dimension.child('SubObject'+side)
    if mode is None or member is None:
        return
    selected = _integer(mode.values[0])
    if selected is None or selected < 0:
        return
    guards = (Guard(mode, mode.values),)
    missing = missing_key(dimension, 'SubObject'+side)
    if missing is not None:
        return None, (Index(missing, argument=1), Index(member)), guards
    return local_attachment(dimension, side, objects)


def specifications(document, *, scope=None):
    from .definitions import has_derived_index
    # Raw ASC omits reserved placed pads and flattens shape properties. Its
    # as_schematic() adapter restores these owned records before binding them.
    if document.representation != 'schematic':
        return
    schematic = document.one('/Schematic')
    for part in symbols(schematic, scope=scope):
        if part.scalar('Enabled') not in (True, 'Y') or part.scalar('PartType') != 0:
            continue
        pattern = part.child('Pattern') or part.parent.child('Pattern')
        if pattern is None:
            continue
        if scope is not None and scope.select(pattern, 'Pads/Pad'):
            # Creating a pad domain can give existing pin numbers their first
            # assignment meaning. Only pins belonging to this symbol are affected.
            scope.include_children(part, 'Pins/Pin')
            scope.include_reference(part, 'symbol-pin-pad')
        pads = _children(pattern, 'Pads', 'Pad')
        for pin in source_records(part, 'Pins/Pin', scope):
            missing = missing_key(pin, 'PadId')
            if missing is not None:
                yield part, None, 'symbol-pin-pad', (Index(missing, argument=1), Index(pin.one('Number'))), (
                    Guard(part.one('PartType'), part.one('PartType').values),)
                continue
            # A generic pin Number can remain literal when there is no local
            # pad domain. The name does not determine assignment ownership.
            # Explicit missing public keys above still have reference meaning.
            if len(pads) <= 2:
                continue
            number = _integer(pin.scalar('Number'))
            if pin.scalar('Enabled') not in (True, 'Y') or number is None or number < 0:
                continue
            target = _at(pads, number) if 1 <= number < len(pads)-1 else None
            yield part, target, 'symbol-pin-pad', (Index(pin.one('Number')),), (
                Guard(part.one('PartType'), part.one('PartType').values),)
    for pattern in footprints(schematic, scope=scope):
        if pattern is None:
            continue
        pads = _children(pattern, 'Pads', 'Pad')
        for connection in source_records(pattern, 'InternalConnections/IntCon', scope):
            for argument, value in enumerate(connection.values):
                missing = missing_key(connection, ('X', 'Y')[argument])
                if missing is not None:
                    yield connection, None, 'pattern-internal-pad-'+str(argument), (
                        Index(missing, argument=1), Index(connection, argument=argument)), ()
                    continue
                number = _integer(value)
                if number is not None and number >= 0:
                    yield connection, _at(pads, number), 'pattern-internal-pad-'+str(argument), (
                        Index(connection, argument=argument),), ()
        for pad in source_records(pattern, 'Pads/Pad', scope):
            index = pad._ordinal()
            if pad.arguments:
                if not has_derived_index(pad):
                    yield pad, pad, 'pad-order', (Index(pad),), ()
            field = pad.child('Number_New')
            if field is not None and field.values == (index,):
                yield pad, pad, 'active-pad-order', (Index(field),), ()
        choices = {}
        for mode, (container, kind) in enumerate(LOCAL_OBJECTS):
            owner = pattern.child(container)
            choices[mode] = owner._child_sequence(kind) if owner is not None else ()
        for shape in source_records(pattern, 'Shapes/Shape', scope):
            field = shape.child('PadId')
            number = _integer(field.values[0]) if field is not None else None
            missing = missing_key(shape, 'PadId')
            if missing is not None:
                yield shape, None, 'pattern-shape-pad', (Index(missing, argument=1), Index(field)), ()
            elif number is not None and number >= 0:
                yield shape, _at(choices[0], number), 'pattern-shape-pad', (Index(field),), ()
        dimensions = source_records(pattern, 'Dimensions/Dimension', scope)
        objects = {kind: dict(enumerate(records[1:-1], 1)) for kind, records in choices.items()} if dimensions else {}
        for dimension in dimensions:
            if dimension.scalar('Enabled') in (False, 'N'):
                continue
            for side in ('1', '2'):
                link = _dimension_link(dimension, side, objects)
                if link is not None:
                    target, indices, guards = link
                    yield dimension, target, 'pattern-dimension-'+side, indices, guards


def issue_collections(source, role):
    """Constrain a known local unresolved index to its own target array."""
    if role == 'symbol-pin-pad':
        pattern = source.child('Pattern') or source.parent.child('Pattern')
        pads = pattern.child('Pads') if pattern is not None else None
        return (pads,) if pads is not None else None
    if role.startswith('pattern-dimension-'):
        side = role[-1]
        mode = _integer(source.scalar('Connected'+side))
        pattern = source.parent.parent
        if mode in (0, 1, 2):
            owner = pattern.child(LOCAL_OBJECTS[mode][0])
            if mode == 1 and owner is not None:
                shape = _real_member(owner.children('Shape'), _integer(source.scalar('SubObject'+side)))
                points = shape.child('Points_New') if shape is not None else None
                return (owner, points) if points is not None else (owner,)
            return (owner,) if owner is not None else None
        if mode == 3:
            pads = pattern.child('Pads')
            if pads is None:
                return None
            pad = _real_member(pads.children('Pad'), _integer(source.scalar('Object'+side)))
            return (pads,) if pad is None else (pads, pad, *(terminal.one('ShapePoints')
                    for terminal in pad.children('PadTerminal') if terminal.child('ShapePoints') is not None))
    if role == 'pattern-shape-pad' or role.startswith('pattern-internal-pad-'):
        pads = source.parent.parent.child('Pads')
        return (pads,) if pads is not None else None
    return None


def valid_dimension_target(reference):
    """Validate ownership and anchor shape after moving or retargeting data."""
    dimension, target = reference.source, reference.target
    pattern = dimension.parent.parent
    side = reference.role[-1]
    mode = _integer(dimension.scalar('Connected'+side))
    if mode in (0, 1, 2):
        owner = pattern.child(LOCAL_OBJECTS[mode][0])
        member = target.parent.parent if target.kind == 'pt' and target.parent.kind == 'Points_New' else target
        if owner is None or member not in owner.children(LOCAL_OBJECTS[mode][1])[1:-1]:
            return False
        if mode == 1:
            kind = _integer(member.scalar('Type', 1))
            return (kind is None or kind >= 1) and ((target.kind == 'pt') == (kind in (8, 9)))
        return mode != 2 or not member.values or member.values[0] not in (False, 'N')
    if mode != 3:
        return False
    terminal = target.parent.parent if target.kind == 'pt' and target.parent.kind == 'ShapePoints' else target
    if terminal.kind != 'PadTerminal' or terminal.parent.kind != 'Pad':
        return False
    pad = terminal.parent
    pads = pattern.child('Pads')
    if pads is None or pad not in pads.children('Pad')[1:-1]:
        return False
    anchor = _integer(dimension.scalar('Point'+side))
    polygon_point = terminal.scalar('Type') == 3 and anchor is not None and anchor > 0
    return (target.kind == 'pt') == polygon_point
