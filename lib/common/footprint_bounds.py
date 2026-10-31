"""Physical footprint envelopes, without text layout, strokes or terminals.

Callers supply current physical pads/drawings and (x, y, outer diameter) holes.
Object eligibility, placement side and visibility belong to the calling domain.
The returned Bounds retains Decimal coordinates. Exact translations therefore
leave its size unchanged and centering does not accumulate numerical drift.

The named shapes use analytical support functions. Rectangle corner radius is
the shorter full dimension times Corner/100, bounded to Corner 0..50 for this
calculation. Polygon points are already physical lengths. No sampled shape table
or text measurements are required.

These conventions can be established with ordinary one-pad footprint fixtures:
vary shape, angle, through/surface status, copper offset and rectangle Corner,
then compare canonical public exports and measured copper geometry. Include
separate holes, text, terminal extensions and different drawing stroke widths
to distinguish a nominal body envelope from other visible geometry.
"""
from decimal import Decimal, localcontext
import math

from .geometry import Bounds, circular_arc_bounds, transform_point, decimal_precision, rotation_components


def _number(value):
    result = value if isinstance(value, Decimal) else Decimal(str(value))
    if not result.is_finite():
        raise ValueError('footprint bounds require finite numbers')
    return result


def _shift(box, x, y):
    return Bounds(box.left+x, box.top+y, box.right+x, box.bottom+y)


def _points(values):
    rows = tuple(tuple(map(_number, row)) for row in values)
    if not rows:
        return None
    xs, ys = zip(*rows)
    return Bounds(min(xs), min(ys), max(xs), max(ys))


def _support(kind, width, height, corner, points, x, y):
    """Maximum scalar projection of one main copper shape in local axes."""
    if kind == 3:
        dx, dy = _number(x), _number(y)
        return max(px*dx+py*dy for px,py in points)
    rx, ry = width/2, height/2
    if kind == 0:
        result = math.hypot(rx*x, ry*y)
    elif kind == 1:
        radius = min(rx, ry)
        result = radius*math.hypot(x,y)+(rx-radius)*abs(x)+(ry-radius)*abs(y)
    elif kind == 2:
        radius = min(width,height)*(min(50,max(0,corner))/100)
        result = (rx-radius)*abs(x)+(ry-radius)*abs(y)+radius*math.hypot(x,y)
    elif kind == 4:
        cap_y = -ry+rx
        cap = cap_y*y+(rx*math.hypot(x,y) if y < 0 else rx*abs(x))
        result = max(rx*abs(x)+ry*y, cap)
    else:  # Fiducials use their two axis-aligned dimensions.
        result = rx*abs(x)+ry*abs(y)
    return _number(result)


def _pad(pad):
    kind = pad['PadShape_New']
    if kind not in (0,1,2,3,4,20):
        return None
    if pad.get('PadWidth_New') is None or pad.get('PadHeight_New') is None:
        return None
    points = [tuple(map(_number,row.values)) for row in pad.select('PadPoints_New/pt')]
    if kind == 3 and not points:
        return None
    declared_width,declared_height = _number(pad['PadWidth_New']),_number(pad['PadHeight_New'])
    width,height = map(float,(declared_width,declared_height))
    if not math.isfinite(width) or not math.isfinite(height) or width < 0 or height < 0:
        raise ValueError('copper dimensions must be finite and nonnegative')
    angle = 0 if kind == 20 else _number(pad['PadAngle'])
    cosine,sine = rotation_components(angle)
    xdir,ydir = (cosine,sine),(-sine,cosine)
    corner = float(pad.get('PadCorner', 0))
    circular = declared_width == declared_height and (kind in (0,1) or kind == 2 and corner >= 50)
    cardinal = (abs(cosine),abs(sine)) in ((1,0),(0,1))
    if kind == 20 or circular or kind in (0,1,2) and cardinal:
        # Rotation cannot change a circle. Cardinal extrema also retain the
        # supplied decimal dimensions instead of passing them through binary64.
        w,h = declared_width,declared_height
        if not (kind == 20 or circular) and not cosine:
            w,h = h,w
        box = Bounds(-w/2,-h/2,w/2,h/2)
    else:
        args = kind,width,height,corner,points
        box = Bounds(-_support(*args,-xdir[0],-xdir[1]),
                     -_support(*args,-ydir[0],-ydir[1]),
                     _support(*args,*xdir),_support(*args,*ydir))
    x,y = _number(pad['X']),_number(pad['Y'])
    if kind != 20 and not pad['SurfacePad']:
        dx,dy = transform_point((pad.get('PadShape_X', 0),pad.get('PadShape_Y', 0)),angle=angle)
        x,y = x+_number(dx),y+_number(dy)
    return _shift(box,x,y)


def _drawing(shape):
    kind = shape['Type']
    if kind <= 0 or kind == 7:
        return None
    points = [tuple(map(_number,row.values)) for row in shape.select('Points_New/pt')]
    if kind != 6:
        return _points(points)
    if len(points) != 3:
        raise ValueError('a footprint arc requires three defining points')
    x,y = points[0]
    relative = [(float(px-x),float(py-y)) for px,py in points]
    box = circular_arc_bounds(*relative)
    return _shift(Bounds(*map(_number,(box.left,box.top,box.right,box.bottom))),x,y)


def physical_bounds(*, pads=(), drawings=(), holes=()):
    """Return the main physical envelope, or None when no object contributes.

    Copper shape offsets apply to through pads; fiducial bounds are axis-aligned.
    Empty or unrecognized copper shapes have no main copper envelope. Terminals and
    drilling do not enlarge it. Hole tuples describe separate mounting objects.
    Inputs are not changed, including rectangle corner settings outside 0..50.
    """
    pads,drawings,holes = tuple(pads),tuple(drawings),tuple(holes)
    values = [value for pad in pads for value in
              (pad['X'],pad['Y'],pad['PadWidth_New'],pad['PadHeight_New'],
               pad['PadAngle'],pad.get('PadCorner', 0),pad.get('PadShape_X', 0),pad.get('PadShape_Y', 0))]
    values.extend(value for pad in pads for row in pad.select('PadPoints_New/pt') for value in row.values)
    values.extend(value for shape in drawings for row in shape.select('Points_New/pt') for value in row.values)
    values.extend(value for hole in holes for value in hole)
    with localcontext() as context:
        context.prec = decimal_precision(values)
        boxes = [box for pad in pads if (box := _pad(pad)) is not None]
        boxes.extend(box for shape in drawings if (box := _drawing(shape)) is not None)
        for x,y,diameter in holes:
            x,y,radius = _number(x),_number(y),_number(diameter)/2
            if radius < 0:
                raise ValueError('mounting-hole diameter must be nonnegative')
            boxes.append(Bounds(x-radius,y-radius,x+radius,y+radius))
        result = None
        for box in boxes:
            result = box if result is None else result.union(box)
        return result
