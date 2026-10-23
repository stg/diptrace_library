"""Schematic orientation projection from current angle values.

Placement uses degrees; drawing and label angles use radians. Footprint pads,
dimensions and 3D geometry have their own angle domains and are not quantized
by this schematic export policy.
"""
import math


def quarter_turns(angle, *, full_turn=360):
    """Normalize and round to 0..3, with half-way ties to an even quarter."""
    if isinstance(angle, bool):
        raise TypeError('an angle must be a number')
    value = float(angle)
    if not math.isfinite(value):
        raise ValueError('an angle must be finite')
    return round((value % full_turn)/(full_turn/4)) % 4


def prepare_angles(document, *, destination, report=None):
    """Quantize schematic angles on an already detached export view."""
    from .conversion import info
    from .dch_records import symbols
    schematic = document.one('/Schematic')
    changed = []

    def project(field, *, index=0, full_turn=math.tau):
        if field is None:
            return
        if index == 0 and len(field.arguments) != 1:
            raise ValueError(f'{field.path}: an angle requires one scalar value')
        value = field.arguments[index]
        if value.kind != 'number' or value.unit:
            raise ValueError(f'{field.path}: an angle requires an unqualified number')
        normalized = quarter_turns(value.value, full_turn=full_turn)*(full_turn/4)
        if float(value.value) != normalized:
            field.set_argument(index, normalized)
            changed.append(field)

    for part in symbols(schematic):
        project(part.child('Angle'), full_turn=360)
        for shape in part.select('Shapes/Shape'):
            project(shape.child('TextAngle'))
        for name in ('ShowRefDes', 'ShowName', 'ShowValue', 'ShowManufacturer', 'ShowDatasheet'):
            project(part.child(name), index=-1)
        for field in part.select('UserFields/UserField'):
            if len(field.arguments) > 3:
                project(field, index=-1)
    for shape in schematic.select('Shapes/Shape'):
        project(shape.child('TextAngle'))
    if changed:
        info(report, 'schematic-angle-normalization', destination,
             'schematic angles are normalized and rounded to quarter turns', changed,
             recoverability='the authoring model retains its current angles; output uses supported schematic orientations')
