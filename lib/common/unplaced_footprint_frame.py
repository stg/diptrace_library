"""Current standalone body frames from the physical footprint geometry.

Text, dimension annotations and drawing strokes do not enlarge this envelope.
An origin or generated-model offset is expressed in the same local frame as
the physical objects. Explicit 3D model transforms have their own units/axes.
These distinctions are observable by converting simple asymmetric footprints
with independently placed text, dimensions, origins and 3D offsets.
"""
from decimal import Decimal, localcontext

from .footprint_bounds import physical_bounds
from .geometry import decimal_precision, stable_midpoint


def normalize_frame(pattern):
    """Center an importer-owned or detached export pattern; never a live edit."""
    pads=pattern.select('Pads/Pad')
    shapes=pattern.select('Shapes/Shape')
    holes=pattern.select('Holes/Hole')
    box=physical_bounds(pads=pads,drawings=shapes,
                        holes=((hole['X'],hole['Y'],hole['Diam']) for hole in holes))
    size=(box.width,box.height) if box is not None else (0,0)
    for name,value in zip(('Width','Height'),size):
        pattern.set_field(name,float(value) if value > 0 else .0001)
    cx,cy=((stable_midpoint(box.left,box.right),stable_midpoint(box.top,box.bottom))
           if box is not None else (0,0))
    if not (cx or cy):
        return
    fields=[(pattern,'OriginX',cx),(pattern,'OriginY',cy)]
    for item in (*pads,*holes):
        fields.extend(((item,'X',cx),(item,'Y',cy)))
    for dimension in pattern.select('Dimensions/Dimension'):
        fields.extend((dimension,name,cx if name.startswith('X') else cy)
                      for name in ('X1','Y1','X2','Y2','XD','YD'))
    model=pattern.one('Model3D')
    fields.extend(((model,'IPC_XOff',cx),(model,'IPC_YOff',cy)))
    points=[point for shape in shapes for point in shape.select('Points_New/pt')]
    values=[cx,cy,*(item[name] for item,name,_ in fields),
            *(value for point in points for value in point.values)]
    # Work at sufficient precision for one translation, then return to the
    # model's ordinary floating values. No input decimal spelling is retained.
    with localcontext() as context:
        context.prec=decimal_precision(values)
        for item,name,offset in fields:
            item.set_field(name,float(Decimal(str(item[name]))-Decimal(str(offset))))
        for point in points:
            point.set_values(*(float(Decimal(str(value))-Decimal(str(offset)))
                               for value,offset in zip(point.values,(cx,cy))))
