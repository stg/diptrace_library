"""Derived text boxes over public drawing fields and injectable font metrics.

Vector layout is self-contained. System-font metrics are an environment input
for older label modernization and calculated output bounds. Callers can supply
a service independently of an installed application or display.
"""
from dataclasses import dataclass
from functools import lru_cache
import math

from ..geometry import aligned_text_box
from ..numbers import calculation_number
from .vector_layout import symbol_vector_text_bounds, footprint_vector_text_bounds


@lru_cache(maxsize=1)
def _system_metrics():
    from .windows import WindowsFontMetrics
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
        return self._system_bounds(shape, kind=10, minimum_size=1.)

    def pattern_bounds(self, shape):
        """Footprint text bounds over all lines and the full authored angle."""
        if shape.scalar('VectorFont') in (True, 'Y'):
            return footprint_vector_text_bounds(shape)
        return self._system_bounds(shape, kind=7, minimum_size=.3)

    def _system_bounds(self, shape, *, kind, minimum_size):
        if shape.scalar('Type') != kind:
            raise ValueError(f'text layout requires Type {kind}')
        if self.measure_system is None:
            raise NotImplementedError('system font measurement service required')
        points = shape.one('Points_New').children('pt')
        if not points:
            raise ValueError(f'{shape.path}: text requires an anchor point')
        anchor = tuple(calculation_number(points[0], i) for i in (0, 1))
        lines = [line.values[0] for line in shape.one('TextLine').children('pt')]
        if not lines:
            return anchor, anchor
        size = max(minimum_size, float(shape.scalar('FontSize')))
        point_size = max(1, round(size*self.resolution/1.2*self.font_scale))
        face = shape.scalar('FontName')
        rows = [self.measure_system(visible_text(line), face, point_size) for line in lines]
        width = max(0., *(row.width/self.resolution for row in rows))
        # The fixed sample supplies row spacing even when the final line is
        # empty. Its actual raw height remains distinct (GDI returns zero).
        sample = self.measure_system('s', face, point_size)
        row_height = sample.height/2.1/self.resolution
        advance = row_height*(calculation_number(shape.one('LineSpacing'))+1)
        last_line = (next((line for line in reversed(lines) if line.replace(' ', '')), None)
                     if kind == 7 else lines[-1])
        height = (0. if last_line is None else (len(lines)-1)*advance +
                  self.measure_system(last_line, face, point_size).height/self.resolution)
        return aligned_text_box(anchor, width, height, shape.scalar('TextHorz'),
                                shape.scalar('TextVert'), float(shape.scalar('TextAngle')))
