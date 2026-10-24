"""Derived text boxes over public drawing fields and injectable font metrics.

Vector layout is self-contained. System-font metrics are an environment input
for older label modernization and calculated output bounds. Callers can supply
a service independently of an installed application or display.
"""
from dataclasses import dataclass
from functools import lru_cache
import math

from ...common.geometry import (aligned_text_box)
from ...common.numbers import (calculation_number)
from .vector_text import (symbol_vector_text_bounds)


@lru_cache(maxsize=1)
def _system_metrics():
    from ...common.text.windows import (WindowsFontMetrics)
    try:
        return WindowsFontMetrics()
    except OSError as error:
        raise NotImplementedError('system-font layout requires a TextLayout measurement provider') from error


def _measure_system(text, family, size):
    return _system_metrics().measure(text, family, size)


def default_layout():
    """Self-contained vector layout with a lazy optional Windows font backend."""
    return TextLayout(measure_system=_measure_system)


def visible_text(text):
    """Remove overbar markers, retaining a doubled marker as a literal tilde."""
    result, marker = [], False
    for character in text:
        if character == '~' and not marker:
            marker = True
        else:
            result.append(character)
            marker = False
    return ''.join(result)


@dataclass(frozen=True)
class TextLayout:
    measure_system: object = None
    resolution: float = 10.
    font_scale: float = 1.

    def __post_init__(self):
        if not math.isfinite(self.resolution) or self.resolution <= 0:
            raise ValueError('text resolution must be positive and finite')
        if not math.isfinite(self.font_scale) or self.font_scale <= 0:
            raise ValueError('font scale must be positive and finite')

    def symbol_bounds(self, shape):
        """Two compatibility box corners; the authoring anchor stays unchanged."""
        if shape.scalar('VectorFont') in (True, 'Y'):
            return symbol_vector_text_bounds(shape)
        if shape.scalar('Type') != 10:
            raise ValueError('symbol text layout requires Type 10')
        if self.measure_system is None:
            raise NotImplementedError('system font measurement service required')
        points = shape.one('Points_New').children('pt')
        if not points:
            raise ValueError(f'{shape.path}: text requires an anchor point')
        anchor = tuple(calculation_number(points[0], i) for i in (0, 1))
        lines = [line.values[0] for line in shape.one('TextLine').children('pt')]
        if not lines:
            return anchor, anchor
        size = max(1., float(shape.scalar('FontSize')))
        point_size = max(1, round(size*self.resolution/1.2*self.font_scale))
        face = shape.scalar('FontName')
        rows = [self.measure_system(visible_text(line), face, point_size) for line in lines]
        width = max(0., *(row.width/self.resolution for row in rows))
        # The fixed sample supplies row spacing even when the final line is
        # empty. Its actual raw height remains distinct (GDI returns zero).
        sample = self.measure_system('s', face, point_size)
        last = self.measure_system(lines[-1], face, point_size)
        row_height = sample.height/2.1/self.resolution
        advance = row_height*(calculation_number(shape.one('LineSpacing'))+1)
        height = (len(lines)-1)*advance + last.height/self.resolution
        return aligned_text_box(anchor, width, height, shape.scalar('TextHorz'),
                                shape.scalar('TextVert'), float(shape.scalar('TextAngle')))
