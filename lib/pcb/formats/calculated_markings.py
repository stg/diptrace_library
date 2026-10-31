"""Complete absent placed-label geometry on a detached output view.

Stored drawings remain current data. Marking settings can also describe a label
without a drawing, so binary/text destinations can reconstruct that optional
geometry. Literal bound text and unplaced library definitions are independent.
"""
from dataclasses import dataclass
from decimal import Decimal, localcontext
import math

from ...common.conversion import info
from ...common.geometry import decimal_precision
from ...common.text.markings import MarkingStyle, marking_width, marking_height
from ..model.markings import field_key, SIDES, USER_FIELD_OFFSET
from ..model.objects import new_pattern_drawing


# Caption priority is independent of metadata serialization order. Explicit
# placements precede automatic placements on each side.
_FIELDS = ((2, 'RefDes'), (1, 'Name'), (3, 'Value'), (7, 'Manufacturer'),
           (4, 'Pattern'), (6, 'Datasheet'))
_OPPOSITE = {1: 3, 2: 3, 3: 2, 4: 5, 5: 4, 6: 3}


def _number(value):
    return value if isinstance(value, Decimal) else Decimal(str(value))


@dataclass(frozen=True)
class _Caption:
    mode: int
    layer: int
    text: str
    alignment: int
    x: object
    y: object
    horizontal: int
    vertical: int
    angle: object
    drawing: object


@dataclass(frozen=True)
class _Placement:
    edge: int
    x: object
    y: object
    horizontal: int
    vertical: int
    angle: object


def _captions(component, board, global_users, layer):
    side = SIDES[layer]
    shapes = {}
    for shape in component.select('Pattern/Shapes/Shape'):
        if shape['Type'] == 7 and shape['Layer'] == layer:
            shapes[shape['TextShow']] = shape
    fields = [(mode, component, name+'_'+side, board, name+'_Global_'+side,
               component.one('Pattern')['Name'] if name == 'Pattern' else component.get(name, ''))
              for mode, name in _FIELDS]
    fields.extend((USER_FIELD_OFFSET+index, field, side,
                   global_users.get(field_key(field['Name'])), side, field['Value'])
                  for index, field in enumerate(component.select('UserFields/UserField')))
    result = []
    for mode, owner, prefix, global_owner, global_prefix, text in fields:
        show = owner.get(prefix+'Show', 0)
        if not show:
            show = global_owner.get(global_prefix+'Show', 2) if global_owner is not None else 2
        existing = shapes.get(mode)
        if show == 2 or existing is not None and not existing.get('MarkingGenerated', False):
            continue
        alignment = owner.get(prefix+'Align', 0)
        if not alignment:
            alignment = global_owner.get(global_prefix+'Align', 7) if global_owner is not None else 7
        result.append(_Caption(mode, layer, text, alignment,
            owner.get(prefix+'X', 0), owner.get(prefix+'Y', 0),
            owner.get(prefix+'Horz', 0), owner.get(prefix+'Vert', 0),
            owner.get(prefix+'Angle', 0), existing))
    return sorted(result, key=lambda caption: caption.alignment == 7)


def _edge(edge, width, height, mirrored, caption):
    if mirrored:
        edge = {4: 5, 5: 4}.get(edge, edge)
    if edge == 1:
        return _Placement(edge, 0, 0, 0, 0, math.pi/2 if height > width else 0)
    if edge == 2:
        return _Placement(edge, 0, -height/2, 0, 1, 0)
    if edge == 3:
        return _Placement(edge, 0, height/2, 0, -1, 0)
    if edge == 4:
        return _Placement(edge, -width/2, 0, 0, 1, math.pi/2)
    if edge == 5:
        return _Placement(edge, width/2, 0, 0, 1, -math.pi/2)
    if edge == 6:
        return _Placement(edge, -width/2 if mirrored else width/2, -height/2,
                          1 if mirrored else -1, 1, 0)
    # Explicit placement and unused compatibility choices retain the public
    # coordinate/alignment fields rather than inventing an automatic anchor.
    return _Placement(edge, caption.x, caption.y, caption.horizontal,
                      caption.vertical, caption.angle)


def _placements(captions, pattern, style, layout, mirrored):
    width, height = _number(pattern['Width']), _number(pattern['Height'])
    values = [width, height, style.font_size]
    values.extend(value for caption in captions for value in (caption.x, caption.y, caption.angle))
    result = []
    with localcontext() as context:
        context.prec = decimal_precision(values)
        for caption in captions:
            edge = caption.alignment
            if edge == 7:
                if not result:
                    edge = (4 if height > width and
                            _number(marking_width(caption.text, style, text_layout=layout)) > width else 2)
                elif len(result) == 1:
                    previous = result[-1][1]
                    if previous.edge == 8:
                        edge = ((4 if previous.x > 0 else 5)
                                if abs(math.cos(float(previous.angle))) < .7 else
                                (2 if previous.y > 0 else 3))
                    else:
                        edge = _OPPOSITE.get(previous.edge, previous.edge)
                else:
                    row_height = _number(marking_height(caption.text, style, text_layout=layout))
                    x = width/2+row_height/3
                    if mirrored:
                        x = -x
                    placement = _Placement(-1, x, -height/2+row_height*Decimal('1.5')*(len(result)-2),
                                           1 if mirrored else -1, -1, 0)
                    result.append((caption, placement))
                    continue
            result.append((caption, _edge(edge, width, height, mirrored, caption)))
    return result


def _drawing(caption, placement, style):
    result = new_pattern_drawing(kind=7)
    values = dict(Layer=caption.layer, FontName=style.font_name, VectorFont=style.vector,
        FontSize=style.font_size, FontScale=style.font_scale, FontWidth=style.font_width,
        FontMono=style.mono, TextShow=caption.mode, MarkingGenerated=True,
        TextAngle=placement.angle, TextHorz=placement.horizontal, TextVert=placement.vertical,
        TextAlign=-1, LineSpacing=1, Width=-1)
    for name, value in values.items():
        result[name] = value
    result.one('TextLine').add('pt', caption.text)
    result.one('Points_New').add('pt', placement.x, placement.y)
    return result


def materialize_markings(board, *, context, destination, report=None):
    """Fill absent calculated drawings, preserving supplied data and identities."""
    global_users = {}
    for field in board.select('Userfields_Global/UserField'):
        global_users.setdefault(field['Value'], field)
    created, unavailable = [], []
    for component in board.select('Components/Component'):
        if not component.get('Enabled', True):
            continue
        for layer in range(len(SIDES)):
            captions = _captions(component, board, global_users, layer)
            if not any(caption.drawing is None for caption in captions):
                continue
            size = (component.get('MarkingFontSize', 5) if component.get('CustomMarkingFont', False)
                    else board['CompFontSize'])
            style = MarkingStyle(font_size=float(size), font_name=board['CompFontName'],
                vector=board['PatternFontVector'], font_width=float(board['PatternFontWidth']),
                font_scale=float(board['PatternFontScale']), mono=board.get('CompFontMono', False))
            pattern = component.one('Pattern')
            try:
                placements = _placements(captions, pattern, style, context.layout, component['BottomSide'])
            except NotImplementedError:
                # The format retains all settings and can recreate these optional
                # drawings in an environment with the required font resources.
                unavailable.append(component)
                continue
            for caption, placement in placements:
                if caption.drawing is None:
                    created.append(pattern.one('Shapes').append(_drawing(caption, placement, style)))
    if created:
        info(report, 'calculated-marking-geometry', destination,
             'Constructed absent component marking drawings from current settings.', created,
             recoverability='the source model is unchanged; text, placement and appearance come from its marking data')
    if unavailable:
        info(report, 'calculated-marking-font-resources', destination,
             'Kept marking settings without calculated drawings requiring unavailable font measurements.',
             tuple(dict.fromkeys(unavailable)),
             recoverability='the receiving editor can reconstruct the drawings; supply context.text_layout to calculate them here')
