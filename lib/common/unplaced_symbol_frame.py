"""Normalize a library symbol's body frame without changing placement facts."""
from decimal import Decimal, localcontext

from .geometry import decimal_precision, stable_midpoint
from .symbol_geometry import symbol_bounds


def normalize_frame(part):
    """Center an importer-owned/detached symbol; ordinary edits stay untouched."""
    box = symbol_bounds(part)
    part['Width'] = float(box.width) if box is not None else 0
    part['Height'] = float(box.height) if box is not None else 0
    cx, cy = ((stable_midpoint(box.left, box.right), stable_midpoint(box.top, box.bottom))
              if box is not None else (0, 0))
    if not (cx or cy):
        return
    fields = [(part, 'Origin_X', cx), (part, 'Origin_Y', cy)]
    for pin in part.select('Pins/Pin'):
        fields.extend(((pin, 'X', cx), (pin, 'Y', cy)))
    points = [point for shape in part.select('Shapes/Shape') for point in shape.select('Points_New/pt')]
    values = [cx, cy, *(owner[name] for owner, name, _ in fields),
              *(value for point in points for value in point.values)]
    with localcontext() as context:
        context.prec = decimal_precision(values)
        for owner, name, offset in fields:
            owner[name] = float(Decimal(str(owner[name]))-Decimal(str(offset)))
        for point in points:
            point.set_values(*(float(Decimal(str(value))-Decimal(str(offset)))
                               for value, offset in zip(point.values, (cx, cy))))
