"""Current footprint frames from physical data, independent of wire dialects."""
from dataclasses import replace
from contextlib import nullcontext
from decimal import Decimal, localcontext

from ...common.conversion import import_notice, info
from ...common.footprint_bounds import physical_bounds
from ...common.footprint_records import PAD, HOLE
from ...common.geometry import decimal_precision, transform_point
from ...common.structural_edits import assembly
from ..model import markings
from .assembly.missing_geometry import DIMENSIONS, unavailable_size


def _number(value):
    return value if isinstance(value, Decimal) else Decimal(str(value))


def resolve_fiducials(board, default):
    settings = board.child('Settings') or board.add('Settings')
    field = settings.child('ShowCompFiducials')
    if field is None:
        settings.add('ShowCompFiducials', default)
        return default
    value = field.values[0]
    if type(value) is not bool:
        raise TypeError('ShowCompFiducials requires a Boolean')
    return value


def _objects(pattern, raw):
    pads = pattern.select('Pads/Pad')
    if raw:
        pads = [pad for pad in pads[1:-1] if pad.get('Number_New', -1) >= 0]
        for pad in pads:
            pad.bind_schema(PAD)
    shapes = [shape for shape in pattern.select('Shapes/Shape') if shape.get('Type', 0) > 0]
    holes = pattern.select('Holes/Hole')
    if raw:
        for hole in holes:
            hole.bind_schema(HOLE)
    return pads, shapes, [hole for hole in holes if hole['Enabled']]


def _fields(record, names):
    return [(record, name) for name in names if record.child(name) is not None]


def _changes(pattern, *, raw, common_fiducials, placement=None, common_only=False,
             frame_origin=None, placement_angle=None):
    pads, shapes, holes = _objects(pattern, raw)
    mode = placement.get('ShowFiducial', 0) if placement is not None and not common_only else 0
    visible = mode == 1 or mode == 0 and common_fiducials
    bounded = [pad for pad in pads
               if (pad['PadShape_New'] != 20 or pattern['Type'] == 20 or visible)
               and not (raw and any(unavailable_size(pad.get(name)) for name in DIMENSIONS))]
    box = physical_bounds(pads=bounded, drawings=shapes,
                          holes=((hole['X'], hole['Y'], hole['Diam']) for hole in holes))
    cx, cy = box.center if box is not None else (Decimal(0), Decimal(0))
    if box is not None and frame_origin is not None:
        cx, cy = map(_number, frame_origin)
    width = box.width if box is not None and box.width > 0 else Decimal('.001')
    height = box.height if box is not None and box.height > 0 else Decimal('.001')
    targets = []
    dx, dy = cx.copy_negate(), cy.copy_negate()
    if cx or cy:
        # Standalone holes/vias have no independent authored origin. Keeping
        # their zero origin also avoids retaining a previous placement frame.
        if pattern['Type'] not in (15, 16):
            targets.extend((record, name, dx if name.endswith('X') else dy)
                           for record, name in _fields(pattern, ('OriginX', 'OriginY')))
        for pad in pads:
            targets.extend((pad, name, delta) for name, delta in (('X', dx), ('Y', dy)))
        for hole in holes:
            targets.extend((hole, name, delta) for name, delta in (('X', dx), ('Y', dy)))
        for dimension in pattern.select('Dimensions/Dimension'):
            if dimension.get('Enabled', True):
                targets.extend((record, name, dx if name.startswith('X') else dy)
                               for record, name in _fields(dimension, ('X1', 'Y1', 'X2', 'Y2', 'XD', 'YD')))
        if placement is not None:
            for prefix in markings.NAMES:
                for side in markings.SIDES:
                    stem = prefix+'_'+side
                    if placement.get(stem+'Align', 0) == 8:
                        targets.extend((record, name, dx if name.endswith('X') else dy)
                                       for record, name in _fields(placement, (stem+'X', stem+'Y')))
            for user in placement.select('UserFields/UserField'):
                for side in markings.SIDES:
                    if user.get(side+'Align', 0) == 8:
                        targets.extend((record, name, dx if name.endswith('X') else dy)
                                       for record, name in _fields(user, (side+'X', side+'Y')))
    point_rows = [row for shape in shapes for row in shape.select('Points_New/pt')] if cx or cy else []
    values = [cx, cy, width, height]
    values.extend(record[name] for record, name, _ in targets)
    values.extend(value for row in point_rows for value in row.values)
    if placement is not None:
        values.extend((placement.get('X', 0), placement.get('Y', 0), placement.get('Angle', 0)))
    if placement_angle is not None:
        values.append(placement_angle)
    pending = {}

    def change(record, name, value):
        field = record.child(name)
        if field is None:
            record.add(name, value)
        elif field.values != (value,):
            pending[field] = (replace(field.arguments[0], value=value, lexeme=None),)

    with localcontext() as context:
        context.prec = decimal_precision(values)
        change(pattern, 'Width', width)
        change(pattern, 'Height', height)
        for record, name, delta in targets:
            change(record, name, _number(record[name])+delta)
        for row in point_rows:
            x, y = row.arguments
            supplied = (replace(x, value=_number(x.value)-cx, lexeme=None),
                        replace(y, value=_number(y.value)-cy, lexeme=None))
            if tuple(value.value for value in supplied) != row.values:
                pending[row] = supplied
        if placement is not None and (cx or cy):
            angle = placement.get('Angle', 0) if placement_angle is None else placement_angle
            cosine, sine = map(_number, transform_point((1, 0), angle=-angle))
            # Compensate every nonzero shift; no renderer rounding cutoff moves
            # the physical design. Cardinal rotations retain exact coordinates.
            change(placement, 'X', _number(placement.get('X', 0))+cx*cosine+cy*sine)
            change(placement, 'Y', _number(placement.get('Y', 0))+cy*cosine-cx*sine)
    return pending


def _apply(owner, pending):
    if not pending:
        return False
    document = owner._owner()
    plan = (document.references._plan_value_changes(tuple(pending.items()))
            if document is not None and document._automatic_structure else None)
    with assembly(document) if document is not None else nullcontext():
        for field, values in pending.items():
            field.set_values(*values)
        if plan is not None:
            document.references.apply_value_change(plan)
    return True


def install_definition_frame(pattern, *, common_fiducials=True):
    """Center cloned XML physical data before supplied placement is authoritative."""
    return _apply(pattern, _changes(pattern, raw=True, common_fiducials=common_fiducials))


def project_frame(component, origin, *, angle, common_fiducials=True, check_number=None):
    """Re-express one owned output component in an explicitly chosen frame.

    The same coordinate facts move as during loading, with placement compensation
    in the destination's angular precision. Empty bodies keep their current frame.
    """
    pending = _changes(component.one('Pattern'), raw=False,
        common_fiducials=common_fiducials, placement=component,
        frame_origin=origin, placement_angle=angle)
    if check_number is not None:
        for arguments in pending.values():
            for argument in arguments:
                check_number(argument.value)
    return _apply(component, pending)


def normalize_frames(board, *, raw=False, common_fiducials=True, common_only=False,
                     destination=None, report=None):
    """Normalize placements, keeping identities and physical board geometry.

    XML constructs its physical style before individual visibility is read.
    Its output view therefore uses common_only=True; loading can then install
    the individual choice without losing a frame displacement at construction.
    """
    changed = []
    for component in board.select('Components/Component'):
        if not component.get('Enabled', True):
            continue
        if _apply(component, _changes(component.one('Pattern'), raw=raw,
                  common_fiducials=common_fiducials, placement=component, common_only=common_only)):
            changed.append(component)
    if changed:
        message = 'Normalized footprint local frames and nominal sizes while retaining board geometry.'
        if destination is None:
            import_notice('info', 'footprint-frame-normalization', message, changed)
        else:
            info(report, 'footprint-frame-normalization', destination, message, changed,
                 recoverability='only the detached output view changes')
