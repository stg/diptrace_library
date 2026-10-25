"""Small geometry operations independent of file readers and document storage.

Bounds describe the defining geometry, without a pen width or text layout.
Circular arcs pass through their three points in order. A repeated first/last
point denotes a circle whose second point is the opposite end of a diameter.
"""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Bounds:
    left: float
    top: float
    right: float
    bottom: float

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
        return self.right - self.left

    @property
    def height(self):
        return self.bottom - self.top

    @property
    def center(self):
        return (self.left + self.right)/2, (self.top + self.bottom)/2

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


def transform_point(point, *, origin=(0, 0), angle=0):
    """Rotate in stored coordinates, then translate; angles are radians.

    Positive angles use (x*cos(a)+y*sin(a), y*cos(a)-x*sin(a)). Exact quarter
    turns use their integer matrices; other angles retain their full value.
    Inputs are not modified and the result is independent of previous results.
    """
    x, y = map(float, point)
    ox, oy = map(float, origin)
    angle = float(angle)
    if not all(math.isfinite(value) for value in (x, y, ox, oy, angle)):
        raise ValueError('point transforms require finite coordinates and angles')
    turn = angle % math.tau
    exact = {0.: (1, 0), math.pi/2: (0, 1), math.pi: (-1, 0), 3*math.pi/2: (0, -1)}
    cosine, sine = exact[turn] if turn in exact else (math.cos(turn), math.sin(turn))
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
