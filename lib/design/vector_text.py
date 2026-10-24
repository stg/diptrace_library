"""Small vector-font metrics API over an independent semantic advance table.

This measures text for compatibility layout; it does not store font contours or
format objects. FontSize/FontWidth/FontScale remain editable document fields.
The built-in profile contains measured character advances and line height.
"""
from dataclasses import dataclass
from functools import lru_cache
import json
import math
from pathlib import Path
import struct
from typing import Mapping

from .asc_policy import calculation_number
from .asc_geometry import aligned_text_box


@dataclass(frozen=True)
class TextMetrics:
    width: float
    height: float


@dataclass(frozen=True)
class VectorFontMetrics:
    advances: Mapping[int, float]
    line_height: float = 1.492
    unit_scale: float = 1.095
    unknown_advance: float = .6
    mono_advance: float = .606
    mono_line_height: float = 1.618

    def measure(self, text, *, size=1., spacing=0., monospaced=False):
        """Measure format vector text, including doubled/markup '~' markers.

        Spacing is in physical units. UTF-16 code units supply character lookup,
        so an unsupported supplementary character occupies two fallback cells.
        The empty-string width retains the compatibility trailing-gap rule;
        the enclosing text-box adapter decides its minimum size.
        """
        unit = float(size)*self.unit_scale
        spacing = float(spacing)
        if not math.isfinite(unit) or not math.isfinite(spacing):
            raise ValueError('text size and spacing must be finite')
        if abs(unit) < .0001:
            unit = .5
        gap = spacing/unit
        raw = text.encode('utf-16-le', errors='surrogatepass')
        codes = [value[0] for value in struct.iter_unpack('<H', raw)]
        position, i = 0., 0
        while i < len(codes):
            code = codes[i]
            i += 1
            if code == ord('~'):
                if i == len(codes) or codes[i] != code:
                    continue
                i += 1
            if monospaced:
                position += self.mono_advance + gap
            elif code in self.advances:
                position += self.advances[code]
                position += gap
            else:
                position += gap
                position += self.unknown_advance
        return TextMetrics((position-gap)*unit, (self.mono_line_height if monospaced else self.line_height)*unit)


@lru_cache(maxsize=1)
def builtin_vector_metrics():
    data = json.loads(Path(__file__).with_name('vector_font_metrics.json').read_text(encoding='utf-8'))
    return VectorFontMetrics({int(code): value for code, value in data['advances'].items()},
        data['line_height'], data['unit_scale'], data['unknown_advance'])


def _vector_pen(size, width_choice):
    pen = .1
    for choice, divisor in ((-3, 12.), (-2, 8.5), (-1, 6.)):
        if abs(width_choice-choice) < .1:
            pen = size/divisor
    return width_choice if width_choice > 0 else pen


def _scaled_width(width, scale):
    return width*scale if round(scale*100) != 100 and width >= .0001 else width


def _text_inputs(shape, kind):
    if shape.scalar('Type') != kind or shape.scalar('VectorFont') not in (True, 'Y'):
        raise NotImplementedError('this layout provider requires vector text of the expected drawing type')
    points = shape.one('Points_New').children('pt')
    if not points:
        raise ValueError(f'{shape.path}: text requires an anchor point')
    anchor = tuple(calculation_number(points[0], index) for index in (0, 1))
    texts = [line.values[0] for line in shape.one('TextLine').children('pt')]
    size = float(shape.scalar('FontSize'))
    pen = _vector_pen(size, calculation_number(shape.one('FontWidth')))
    scale = calculation_number(shape.one('FontScale'))
    return anchor, texts, size, pen, scale


def pattern_vector_text_bounds(shape, *, font=None):
    """Two physical box corners for the legacy ASC footprint text view.

    This view uses the first text line and a rounded quarter-turn angle. The
    complete TextLine collection, authoring angle and anchor stay untouched.
    Horizontal/vertical alignment use -1/start, 0/center, 1/end.
    """
    anchor, texts, size, pen, scale = _text_inputs(shape, 7)
    if not texts:
        return anchor, anchor
    metrics = (font or builtin_vector_metrics()).measure(texts[0], size=size/1.3, spacing=pen*2,
                                                       monospaced=shape.scalar('FontMono', False))
    width, height = max(0., _scaled_width(metrics.width, scale)+pen), metrics.height+pen
    angle = round(float(shape.scalar('TextAngle'))/(math.pi/2))*(math.pi/2)
    return aligned_text_box(anchor, width, height, shape.scalar('TextHorz'), shape.scalar('TextVert'), angle)


def symbol_vector_text_bounds(shape, *, font=None):
    """Symbol/schematic vector text box, including all lines and the full angle.

    LineSpacing determines the separation between baseline rows. This is a
    derived compatibility box over editable public fields, never stored geometry.
    """
    anchor, texts, size, pen, scale = _text_inputs(shape, 10)
    if not texts:
        return anchor, anchor
    font = font or builtin_vector_metrics()
    rows = [font.measure(text, size=size/1.3, spacing=pen*2,
                         monospaced=shape.scalar('FontMono', False)) for text in texts]
    width = max(0., *(_scaled_width(row.width, scale)+pen for row in rows))
    height = rows[0].height+pen
    spacing = calculation_number(shape.one('LineSpacing'))
    height += (rows[0].height/2.45+pen)*(spacing+1)*(len(rows)-1)
    return aligned_text_box(anchor, width, height, shape.scalar('TextHorz'), shape.scalar('TextVert'),
                        float(shape.scalar('TextAngle')))
