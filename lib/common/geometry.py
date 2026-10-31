"""Small geometry operations independent of file readers and document storage.

Bounds describe the defining geometry, without a pen width or text layout.
Circular arcs pass through their three points in order. A repeated first/last
point denotes a circle whose second point is the opposite end of a diameter.
"""
from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction
import math


_TURN = Decimal(str(math.tau))
_HALF_TURN = Decimal(str(math.pi))
_CARDINALS = {Decimal(str(angle)): components for angle, components in (
    (0, (1, 0)), (math.pi/2, (0, 1)), (math.pi, (-1, 0)), (3*math.pi/2, (0, -1)))}


def decimal_precision(values):
    """Precision for exact coordinate sums plus binary64 angular factors."""
    numbers = [value if isinstance(value, Decimal) else Decimal(str(value))
               for value in values if value is not None and value != 0]
    if any(not value.is_finite() for value in numbers):
        raise ValueError('geometry coordinates must be finite')
    return (max(50, max(value.adjusted() for value in numbers)
                - min(value.as_tuple().exponent for value in numbers)+34)
            if numbers else 50)


def _extent(first, last, *, midpoint=False):
    if not isinstance(first, Decimal) and not isinstance(last, Decimal):
        return (first+last)/2 if midpoint else last-first
    first, last = (value if isinstance(value, Decimal) else Decimal(str(value))
                   for value in (first,last))
    with localcontext() as context:
        context.prec = decimal_precision((first,last))
        return (first+last)/2 if midpoint else last-first


@dataclass(frozen=True)
class Bounds:
    left: float | Decimal
    top: float | Decimal
    right: float | Decimal
    bottom: float | Decimal

    @classmethod
    def from_points(cls, points):
        points = [(float(x), float(y)) for x, y in points]
        if not points:
            return None
        if not all(math.isfinite(v) for point in points for v in point):
            raise ValueError('geometry coordinates must be finite')
        xs, ys = zip(*points)
        return cls(min(xs), min(ys), max(xs), max(ys))

    @property
    def width(self):
        return _extent(self.left,self.right)

    @property
    def height(self):
        return _extent(self.top,self.bottom)

    @property
    def center(self):
        return (_extent(self.left,self.right,midpoint=True),
                _extent(self.top,self.bottom,midpoint=True))

    def union(self, other):
        return Bounds(min(self.left, other.left), min(self.top, other.top),
                      max(self.right, other.right), max(self.bottom, other.bottom))


def circular_arc_bounds(start, middle, end):
    """Bound an arc by its endpoints and the cardinal extrema on its sweep.

    Solve the circumcenter using vectors from the first point. This avoids
    slope divisions, including for horizontal and vertical chords. Collinear
    points have their ordinary point bounds.
    """
    points = [tuple(map(float, p)) for p in (start, middle, end)]
    bounds = Bounds.from_points(points)
    (ax, ay), (bx, by), (cx, cy) = points
    if points[0] == points[2]:
        ox, oy = (ax+bx)/2, (ay+by)/2
        radius = math.hypot(bx-ax, by-ay)/2
        return Bounds(ox-radius, oy-radius, ox+radius, oy+radius)
    ux, uy, vx, vy = bx-ax, by-ay, cx-ax, cy-ay
    cross = ux*vy - uy*vx
    if cross == 0:
        return bounds
    u2, v2 = ux*ux+uy*uy, vx*vx+vy*vy
    dx, dy = (u2*vy-v2*uy)/(2*cross), (ux*v2-vx*u2)/(2*cross)
    ox, oy = ax+dx, ay+dy
    radius = math.hypot(dx, dy)
    direction = 1 if cross > 0 else -1
    first = math.atan2(ay-oy, ax-ox)
    last = math.atan2(cy-oy, cx-ox)
    sweep = (direction*(last-first)) % math.tau
    candidates = ((0, (ox+radius, oy)), (math.pi/2, (ox, oy+radius)),
                  (math.pi, (ox-radius, oy)), (3*math.pi/2, (ox, oy-radius)))
    extrema = [point for angle, point in candidates
               if (direction*(angle-first)) % math.tau <= sweep]
    return bounds.union(Bounds.from_points(extrema)) if extrema else bounds


def unequal_extents(first, opposite, *, tolerance, scale=(1, 1)):
    """Compare scaled box spans using authored decimal values exactly.

    Floating subtraction near a cutoff must not make translation select a
    different representation. Contour sampling can still use floating math.
    """
    limit = Fraction(str(tolerance))
    if limit < 0:
        raise ValueError('extent tolerance must be nonnegative')
    left, top = (Fraction(str(value)) for value in first)
    right, bottom = (Fraction(str(value)) for value in opposite)
    sx, sy = (Fraction(str(value)) for value in scale)
    width, height = abs((right-left)*sx), abs((bottom-top)*sy)
    return abs(width-height) > limit


def ellipse_points(first, opposite, *, segments=30, closed=False):
    """Sample an axis-aligned ellipse from its opposite bounding corners."""
    if not isinstance(segments, int) or segments < 3:
        raise ValueError('an ellipse needs at least three segments')
    box = Bounds.from_points((first, opposite))
    x, y = box.center
    rx, ry = box.width/2, box.height/2
    points = tuple((x+rx*math.cos(i*math.tau/segments), y+ry*math.sin(i*math.tau/segments))
                   for i in range(segments))
    return points+(points[0],) if closed else points


def rotation_components(angle):
    """Return cosine/sine with exact cardinal and reflection symmetries.

    Reduce the decimal angle before evaluating binary64 trigonometry. In
    particular, theta and turn-theta use the same magnitude; a float modulo
    followed by an independent cosine would introduce unequal reflected bounds.
    """
    value = angle if isinstance(angle, Decimal) else Decimal(str(angle))
    if not value.is_finite():
        raise ValueError('rotation requires a finite angle')
    with localcontext() as context:
        context.prec = decimal_precision((value, _TURN))
        magnitude, sign = value.copy_abs() % _TURN, -1 if value < 0 else 1
        if magnitude in _CARDINALS:
            cosine, sine = _CARDINALS[magnitude]
        else:
            if magnitude > _HALF_TURN:
                magnitude, sign = _TURN-magnitude, -sign
            if magnitude in _CARDINALS:
                cosine, sine = _CARDINALS[magnitude]
            else:
                radians = float(magnitude)
                cosine, sine = math.cos(radians), math.sin(radians)
    return cosine, sign*sine


def reflected_angle(angle):
    """Reflect an angle into one positive turn without quantizing its value."""
    value = angle if isinstance(angle, Decimal) else Decimal(str(angle))
    if not value.is_finite():
        raise ValueError('reflection requires a finite angle')
    with localcontext() as context:
        context.prec = decimal_precision((value, _TURN))
        turn = value % _TURN
        if turn < 0:
            turn += _TURN
        # Their canonical binary64 spellings are not all exact multiples of
        # the decimal period. Reflect known quarter turns by their matrices.
        cardinals = tuple(_CARDINALS)
        if turn in _CARDINALS:
            return cardinals[-cardinals.index(turn) % 4]
        return _TURN-turn if turn else turn


def transform_point(point, *, origin=(0, 0), angle=0):
    """Rotate in stored coordinates, then translate; angles are radians.

    Positive angles use (x*cos(a)+y*sin(a), y*cos(a)-x*sin(a)). Exact quarter
    turns use their integer matrices; other angles retain their full value.
    Inputs are not modified and the result is independent of previous results.
    """
    x, y = map(float, point)
    ox, oy = map(float, origin)
    if not all(math.isfinite(value) for value in (x, y, ox, oy)):
        raise ValueError('point transforms require finite coordinates and angles')
    cosine, sine = rotation_components(angle)
    return ox+x*cosine+y*sine, oy+y*cosine-x*sine


def polar_rotate(point, angle):
    """Clockwise rotation with the legacy binary64 polar calculation boundary."""
    x, y = point
    radius = math.sqrt(x*x+y*y)
    if x:
        slope = y/x
        magnitude = abs(slope)
        direction = (math.pi/2-math.atan(1/magnitude) if magnitude > 1
                     else math.atan(magnitude))
        direction = math.copysign(direction, slope)+(math.pi if x < 0 else 0)
    else:
        direction = math.pi/2 if y > 0 else -math.pi/2
    direction -= angle
    return radius*math.cos(direction), radius*math.sin(direction)


def aligned_text_box(anchor, width, height, horizontal, vertical, angle):
    """Place a rectangle from its aligned pivot and two edge vectors.

    Polar pivot placement preserves compatibility rounding at decimal ties.
    These are temporary geometric values, not format drawing records.
    """
    dx = -width if horizontal > 0 else 0. if horizontal < 0 else -width/2
    dy = -height if vertical > 0 else 0. if vertical < 0 else -height/2
    pivot = polar_rotate((dx, dy), angle)
    origin = anchor[0]+pivot[0], anchor[1]+pivot[1]
    across = width*math.cos(-angle), width*math.sin(-angle)
    down = height*math.cos(math.pi/2-angle), height*math.sin(math.pi/2-angle)
    far = origin[0]+across[0], origin[1]+across[1]
    corners = (origin, far, (far[0]+down[0], far[1]+down[1]),
               (origin[0]+down[0], origin[1]+down[1]))
    return ((min(p[0] for p in corners), min(p[1] for p in corners)),
            (max(p[0] for p in corners), max(p[1] for p in corners)))
