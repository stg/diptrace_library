"""Small compatibility geometry operations, separate from authoring bounds."""
import math


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
