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
