"""Legacy ASC pad contours, kept separate from editable modern pad geometry.

ASC carries two views of a pad. The modern shape remains the design truth; this
module makes the older polygon view expected by ASC consumers. Sampling
and legacy dimension rules here must not be used as physical design bounds.
"""
from dataclasses import dataclass
import math
from .asc_geometry import polar_rotate


@dataclass(frozen=True)
class PadContour:
    shape: int
    width: float
    height: float
    points: tuple[tuple[float, float], ...]


def requires_modern_points(legacy, modern):
    """Whether ASC emits its additional ``PadPoints_New`` array."""
    return len(legacy) != len(modern) or any(
        a[0]-b[0] >= .0001 and a[1]-b[1] < .0001
        for a, b in zip(legacy, modern))


def _arc(center, radius, start, end, steps, *, interior=False):
    first, last = (1, steps) if interior else (0, steps + 1)
    return [(center[0] + radius * math.cos(start + (end-start)*i/steps),
             center[1] + radius * math.sin(start + (end-start)*i/steps))
            for i in range(first, last)]


def legacy_pad_contour(shape, width, height, corner, points=(), angle=0):
    """Build the old contour view; ``angle`` is clockwise rotation in radians.

    This is our geometric implementation of behavior checked against the format
    contour helper. It deliberately includes its sampled outlines and positive
    half-extent dimension convention, including asymmetric custom polygons.
    Inputs are calculation floats, not the model's exact decimal wire values.
    """
    shape = int(shape)
    width, height, corner, angle = map(float, (width, height, corner, angle))
    outline = [tuple(map(float, point)) for point in points]
    a, b = width/2, height/2
    if shape == 0 and abs(width-height) > .02:
        outline = [(a*math.cos(i*math.pi/10), b*math.sin(i*math.pi/10))
                   for i in range(20)]
        shape = 3
    elif shape == 1 and abs(width-height) > .02:
        if width > height:
            outline = (_arc((a-b, 0), b, math.pi/2, -math.pi/2, 7) +
                       _arc((-a+b, 0), b, 3*math.pi/2, math.pi/2, 7))
        else:
            outline = (_arc((0, b-a), a, math.pi, 0, 7) +
                       _arc((0, -b+a), a, 0, -math.pi, 7))
        shape = 3
    elif shape == 2:
        radius = min(width, height)*corner/100
        if corner < .001:
            outline = [(-a, -b), (a, -b), (a, b), (-a, b)]
        else:
            outline = []
            # Each edge contributes its endpoints and the following rounded
            # corner contributes five interior samples, in public ASC order.
            corners = ((a-radius, -b+radius), (a-radius, b-radius),
                       (-a+radius, b-radius), (-a+radius, -b+radius))
            edges = (((-a+radius, -b), (a-radius, -b)),
                     ((a, -b+radius), (a, b-radius)),
                     ((a-radius, b), (-a+radius, b)),
                     ((-a, b-radius), (-a, -b+radius)))
            for i, (center, edge) in enumerate(zip(corners, edges)):
                outline.extend(edge)
                outline.extend(_arc(center, radius, (i-1)*math.pi/2,
                                    i*math.pi/2, 6, interior=True))
        shape = 3
    elif shape == 4:
        radius = a
        center = (0, -b+radius)
        outline = [(a, b), (-a, b), (-a, center[1])]
        outline.extend(_arc(center, radius, math.pi, 2*math.pi, 12)[1:])
        if center[1] > b+.0001:
            # The format legacy view scales the curved portion for short D
            # shapes; the modern dimensions and authoring shape stay intact.
            ratio = height/radius
            outline[2:] = [(x, -b+(y+b)*ratio) for x, y in outline[2:]]
        shape = 3
    if shape == 3 and outline:
        # Polar rotation and reciprocal angle reduction matter even at zero
        # angle: binary64 reconstruction can move an ASC rounding boundary.
        outline = [polar_rotate(point, angle) for point in outline]
        width = max(0., *(2*x for x, _ in outline))
        height = max(0., *(2*y for _, y in outline))
    return PadContour(shape, width, height, tuple(outline))
