"""Calculated vector text boxes for schematic and footprint drawings."""
import math
from ...common.numbers import (calculation_number)
from ...common.geometry import (aligned_text_box)
from ...common.text.vector import (builtin_vector_metrics)


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
