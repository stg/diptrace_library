"""Label appearance and text measurements shared by design families."""
from dataclasses import dataclass

from .vector import builtin_vector_metrics
from .vector_layout import _vector_pen, _scaled_width


@dataclass(frozen=True)
class MarkingStyle:
    font_size: float = 2
    font_name: str = ''
    vector: bool = True
    font_width: float = -2.
    font_scale: float = 1.
    font_color: int = 0
    pen_width: float = 1.
    mono: bool = False


def marking_width(text, style, *, text_layout=None, point_size_divisor=1.2):
    if style.vector:
        pen = _vector_pen(style.font_size, style.font_width)
        metrics = builtin_vector_metrics().measure(text, size=style.font_size/1.3, spacing=pen*2, monospaced=style.mono)
        return _scaled_width(metrics.width, style.font_scale)+pen
    if text_layout is None or text_layout.measure_system is None:
        raise NotImplementedError('system font measurements are required for automatic marking placement')
    size = max(1, round(style.font_size*text_layout.resolution/point_size_divisor*text_layout.font_scale))
    return text_layout.measure_system(text, style.font_name, size).width/text_layout.resolution


def marking_height(text, style, *, text_layout=None, point_size_divisor=1.2):
    if style.vector:
        pen = _vector_pen(style.font_size, style.font_width)
        return builtin_vector_metrics().measure(text, size=style.font_size/1.3, spacing=pen*2, monospaced=style.mono).height+pen
    if text_layout is None or text_layout.measure_system is None:
        raise NotImplementedError('system font measurements are required for automatic marking rows')
    size = max(1, round(style.font_size*text_layout.resolution/point_size_divisor*text_layout.font_scale))
    return text_layout.measure_system(text, style.font_name, size).height/text_layout.resolution
