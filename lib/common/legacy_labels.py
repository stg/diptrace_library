"""Neutral inputs and anchor math for older two-slot label formats."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class LegacyLabelSlot:
    mode: int = 0
    alignment: int = 0
    user_field: int = -1
    x_shift: float = 0.
    y_shift: float = 0.


def label_anchor(alignment, shifts, dimensions):
    """Return X/Y, horizontal/vertical alignment and angle for a named edge.

    Input shifts and dimensions use the caller's local coordinate frame. Unknown
    choices have no inferred anchor. Family policy decides whether to retain an
    automatic choice or store the resulting explicit placement.
    """
    width, height = map(float, dimensions)
    x, y = map(float, shifts)
    positions = {
        1: (-y, -x, 0, 0, math.pi/2) if height > width else (x, -y, 0, 0, 0.),
        2: (x, -height/2-y, 0, 1, 0.),
        3: (x, height/2+y, 0, -1, 0.),
        4: (-width/2-y, -x, 0, 1, math.pi/2),
        5: (width/2+y, -x, 0, -1, math.pi/2),
        6: (width/2+x, -height/2-y, -1, 1, 0.),
    }
    return positions.get(alignment)
