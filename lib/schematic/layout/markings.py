"""Calculated component labels over current text, choices and drawing appearance.

Label settings and component text are the authoring inputs. A cached drawing may
provide its own retained appearance fields; new drawings use explicit defaults.
"""
from dataclasses import dataclass
import math

from .legacy_labels import (LabelSettings, label_side)
from ...common.model import (Element)
from ...common.text.vector import (builtin_vector_metrics)
from .vector_text import (_vector_pen, _scaled_width)
from ..model.user_fields import (global_user_field_choice)


def _text_field(part, name):
    field = part.one(name)
    if len(field.arguments) != 1 or field.children():
        raise ValueError(f'{field.path}: expected one scalar text value')
    value = field.arguments[0]
    if value.kind != 'string' or value.unit:
        raise TypeError(f'{field.path}: marking content requires text')
    return value.value


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


def common_marking_family(schematic):
    """Infer a family only when retained active generated labels agree."""
    families = {shape.scalar('FontName', '') for part in schematic.select('Components/Part')
                if part.scalar('Enabled', True) not in (False, 'N')
                for shape in part.select('Shapes/Shape')
                if shape.scalar('Enabled', True) not in (False, 'N')
                and shape.scalar('MarkingGenerated') in (True, 'Y')}
    if any(not isinstance(family, str) for family in families):
        raise TypeError('marking font families must be text')
    return next(iter(families)) if len(families) == 1 else ''


def resolve_marking_style(document, style=None):
    """Use overrides, stored choices, common label family and standard defaults."""
    if style is not None:
        if not isinstance(style, MarkingStyle):
            raise TypeError('marking_style must be a MarkingStyle')
        return style
    schematic = document.one('/Schematic')
    settings = schematic.one('Settings')
    family = (settings.scalar('MarkingFontName') if settings.child('MarkingFontName') is not None
              else common_marking_family(schematic))
    if not isinstance(family, str):
        raise TypeError('marking font family must be text')
    return MarkingStyle(
        font_size=settings.scalar('PartFontSize', 2),
        mono=settings.scalar('PartFontMono', False),
        font_name=family,
        vector=schematic.scalar('PartFontVector', True) in (True, 'Y'),
        font_width=float(schematic.scalar('PartFontWidth', -2)),
        font_scale=float(schematic.scalar('PartFontScale', 1)),
        font_color=settings.scalar('PartFontColor', 0) if settings.scalar('UsePartFontColor', False) in (True, 'Y') else 0)


def apply_marking_style(document, style):
    """Apply an explicit appearance override to an already detached view."""
    if style is None:
        return
    schematic = document.one('/Schematic')
    for name, value in (('PartFontVector', style.vector), ('PartFontWidth', style.font_width),
                        ('PartFontScale', style.font_scale)):
        schematic.set_field(name, value)
    settings = schematic.child('Settings')
    if settings is None:
        return
    settings.set_field('PartFontSize', style.font_size)
    settings.set_field('PartFontMono', style.mono)
    settings.set_field('PartFontColor', style.font_color)
    settings.set_field('MarkingFontName', style.font_name)


def marking_width(text, style, *, text_layout=None):
    if style.vector:
        pen = _vector_pen(style.font_size, style.font_width)
        metrics = builtin_vector_metrics().measure(text, size=style.font_size/1.3, spacing=pen*2, monospaced=style.mono)
        return _scaled_width(metrics.width, style.font_scale)+pen
    if text_layout is None or text_layout.measure_system is None:
        raise NotImplementedError('system font measurements are required for automatic marking placement')
    size = max(1, round(style.font_size*text_layout.resolution/1.2*text_layout.font_scale))
    return text_layout.measure_system(text, style.font_name, size).width/text_layout.resolution


def marking_height(text, style, *, text_layout=None):
    if style.vector:
        pen = _vector_pen(style.font_size, style.font_width)
        return builtin_vector_metrics().measure(text, size=style.font_size/1.3, spacing=pen*2, monospaced=style.mono).height+pen
    if text_layout is None or text_layout.measure_system is None:
        raise NotImplementedError('system font measurements are required for automatic marking rows')
    size = max(1, round(style.font_size*text_layout.resolution/1.2*text_layout.font_scale))
    return text_layout.measure_system(text, style.font_name, size).height/text_layout.resolution


def build_marking(text, font_type, settings, *, dimensions, style=MarkingStyle(),
                  pin_lengths=None, text_layout=None, template=None, show_part=False):
    """Create/update one marking with a local anchor; source elements stay intact.

    ``settings`` is a resolved LabelSettings (visibility and global inheritance
    have already been handled). ``pin_lengths`` maps occupied orientations to
    their maximum extension. Position 8 preserves explicit coordinates/angle.
    """
    result = template.clone() if template is not None else Element('Shape', 0)
    return _write_marking(result, text, font_type, settings, dimensions=dimensions,
                          style=style, pin_lengths=pin_lengths, text_layout=text_layout,
                          new=template is None, show_part=show_part)


def _write_marking(result, text, font_type, settings, *, dimensions, style,
                   pin_lengths=None, text_layout=None, new=False, show_part=False):
    pin_lengths = pin_lengths or {}
    width, height = dimensions
    position = settings.position
    if position == 7:
        preferred = 4 if height > width and marking_width(text, style, text_layout=text_layout) > width else 2
        position = label_side(preferred, pin_lengths)
    placements = {
        1: (0., 0., 0, 0, math.pi/2 if height > width else 0.),
        2: (0., -height/2-pin_lengths.get(1, 0.), 0, 1, 0.),
        3: (0., height/2+pin_lengths.get(3, 0.), 0, -1, 0.),
        4: (-width/2-pin_lengths.get(0, 0.), 0., 0, 1, math.pi/2),
        5: (width/2+pin_lengths.get(2, 0.), 0., 0, -1, math.pi/2),
        6: (width/2, -height/2, -1, 1, 0.),
        8: (settings.x, settings.y, settings.horizontal, settings.vertical, settings.angle),
    }
    if position not in placements:
        raise ValueError(f'unsupported marking position {position}')
    x, y, horizontal, vertical, angle = placements[position]
    if new:
        for name, value in (('FontColor', style.font_color), ('PenWidth', style.pen_width),
            ('TextAlign', -1), ('LineSpacing', 1.), ('Group', -1),
            ('Locked', False), ('MarkingGenerated', True), ('FontType', font_type)):
            result.set_field(name, value)
    for name, value in (('Enabled', True), ('Type', 10),
        ('FontSize', style.font_size), ('FontName', style.font_name),
        ('FontMono', style.mono),
        ('VectorFont', style.vector), ('FontWidth', style.font_width), ('FontScale', style.font_scale),
        ('TextAngle', angle), ('TextHorz', horizontal), ('TextVert', vertical), ('ShowPart', show_part)):
        result.set_field(name, value)
    points = result.child('Points_New') or result.add('Points_New')
    if points.children('pt'):
        points.children('pt')[0].set_values(x, y)
    else:
        points.add('pt', x, y)
    lines = result.child('TextLine') or result.add('TextLine')
    existing = lines.children('pt')
    if existing:
        existing[0].set_values(text)
        for line in existing[1:]:
            line.detach()
    else:
        lines.add('pt', text)
    return result


def generate_markings(part, schematic, *, style, text_layout=None, compact=False):
    """Return detached drawing records rebuilt from current component labels.

    Explicit placements precede automatic placements. Automatic text uses a free
    edge, the opposite edge, then additional rows beside the component.
    ``compact`` selects the active legacy drawing view without deleting facts
    from the source model.
    """
    source = part.one('Shapes').children('Shape')
    drawings = [node.clone() for node in source]
    return _generate_markings(part, schematic, drawings, style=style,
                              text_layout=text_layout, compact=compact)


def update_markings(part, schematic, *, style, text_layout=None, protected=()):
    """Refresh calculated labels on an export view, retaining drawing identities."""
    collection = part.one('Shapes')
    drawings = _generate_markings(part, schematic, collection.children('Shape'),
                                  style=style, text_layout=text_layout, protected=protected)
    for drawing in drawings:
        if drawing.parent is None:
            collection.append(drawing)


def _generate_markings(part, schematic, drawings, *, style, text_layout=None, compact=False, protected=()):
    from dataclasses import replace
    from ...common.numbers import (calculation_number)
    from ..formats.compatibility import (_empty_inactive_drawing)
    pins = [pin for pin in part.select('Pins/Pin') if pin.scalar('Enabled') in (True, 'Y')]
    lengths = {}
    for pin in pins:
        orientation = pin.scalar('Orientation')
        orientation = orientation if 0 <= orientation < 4 else 0
        lengths[orientation] = max(lengths.get(orientation, 0.), calculation_number(pin.one('Length')))
    dimensions = tuple(calculation_number(part.one(name)) for name in ('Width', 'Height'))
    measurement_style = style
    if part.scalar('CustomMarkingFont') in (True, 'Y'):
        style = replace(style, font_size=part.scalar('MarkingFontSize'))
    if style.vector:
        measurement_style = style
    definitions = (('ShowRefDes', 2, part.values[1]), ('ShowName', 1, part.values[0]),
                   ('ShowValue', 3, _text_field(part, 'Value')), ('ShowManufacturer', 5, _text_field(part, 'Manufacturer')),
                   ('ShowDatasheet', 6, _text_field(part, 'Datasheet')))
    definitions = [(name, kind, text, part.one(name), 0, schematic.one(name+'_Global').values,
                    name in ('ShowRefDes', 'ShowName')) for name, kind, text in definitions]
    users = part.one('UserFields').children('UserField')
    overrides = schematic.one('ShowUserfield_Global').children('pt')
    for index, field in enumerate(users):
        override = global_user_field_choice(field.values[0],(row.values for row in overrides))
        definitions.append(('UserField', 20+index, field.values[1], field, 3, override, False))
    for shape in drawings:
        if (shape.scalar('MarkingGenerated') in (True, 'Y') and shape.scalar('FontType', 0) >= 20+len(users)):
            shape.set_field('Enabled', False)
            shape.set_field('Type', 0)
    choices = []
    for name, kind, text, node, prefix, global_values, named in definitions:
        values = list(node.values[prefix:])
        for index in range(len(values)-3, len(values)):
            values[index] = calculation_number(node, prefix+index)
        setting = LabelSettings.from_values(values, named=named)
        global_state, global_position = global_values[0], global_values[-1]
        state = setting.state or global_state
        setting = replace(setting, state=state, position=setting.position or global_position)
        matches = [(index, shape) for index, shape in enumerate(drawings)
                   if shape.scalar('FontType') == kind and
                   (shape.scalar('MarkingGenerated') in (True, 'Y') or
                    shape.scalar('Enabled') in (True, 'Y') and shape.scalar('Type') == 10)]
        existing = matches[-1] if matches else None
        if existing and existing[1].scalar('MarkingGenerated') not in (True, 'Y'):
            continue  # An authored marking keeps its own placement and style.
        if state == 2:
            if existing:
                existing[1].set_field('Enabled', False)
                existing[1].set_field('Type', 0)
            continue
        variant = setting.name_variant or (global_values[1] if len(global_values) == 3 else 0)
        show_part = False
        if name in ('ShowName', 'ShowRefDes') and part.scalar('AllowParts') in (True, 'Y') and variant == 1:
            suffix = part.scalar('PartName' if name == 'ShowName' else 'PartDescriptor')
            if suffix.replace(' ', ''):
                text += f' ({suffix})' if name == 'ShowName' else '.'+suffix
                show_part = True
        choices.append((setting.position == 7, kind, text, setting, existing, show_part))
    choices.sort(key=lambda item: item[0])
    previous, previous_shape = None, None
    column_extension = lengths.get(2, 0.)
    for ordinal, (automatic, kind, text, setting, existing, show_part) in enumerate(choices):
        drawing_style, layout_style = style, measurement_style
        settings = schematic.child('Settings')
        if (existing is not None and not style.font_name and
                (settings is None or settings.child('MarkingFontName') is None)):
            # A stored drawing family is an appearance setting when the document
            # has no global family. Regenerating its text must not erase it.
            family = existing[1].scalar('FontName', '')
            drawing_style = replace(style, font_name=family)
            layout_style = replace(measurement_style, font_name=family)
        if automatic and ordinal:
            if ordinal > 1:
                row_height = marking_height(text, layout_style, text_layout=text_layout)
                if previous == 5:
                    column_extension += row_height*1.2
                setting = replace(setting, position=8, horizontal=-1, vertical=-1,
                    x=dimensions[0]/2+column_extension+row_height/3,
                    y=-dimensions[1]/2+row_height/3+row_height*1.5*(ordinal-2), angle=0.)
                resolved_side = -1
            else:
                side = {1: 3, 2: 3, 3: 2, 4: 5, 5: 4, 6: 3}.get(previous)
                if previous == 8:
                    anchor = previous_shape.one('Points_New/pt[1]').values
                    if math.cos(float(previous_shape.scalar('TextAngle'))) < .7:
                        side = 4 if anchor[0] > 0 else 5
                    else:
                        side = 2 if anchor[1] > 0 else 3
                if side is None:
                    raise ValueError('automatic label has no previous edge or anchor')
                setting = replace(setting, position=side)
                resolved_side = side
        else:
            resolved_side = setting.position
        if setting.position == 7:
            preferred = 4 if dimensions[1] > dimensions[0] and marking_width(text, layout_style, text_layout=text_layout) > dimensions[0] else 2
            setting = replace(setting, position=label_side(preferred, lengths))
            resolved_side = setting.position
        vacant = None
        if existing is None:
            vacant = next((node for node in drawings if node not in protected
                           and _empty_inactive_drawing(node)), None)
        shape = existing[1] if existing else vacant if vacant is not None else Element('Shape', 0)
        _write_marking(shape, text, kind, setting, dimensions=dimensions, style=drawing_style,
                       pin_lengths=lengths, text_layout=text_layout, new=existing is None,
                       show_part=show_part)
        if existing is None and vacant is None:
            drawings.append(shape)
        previous, previous_shape = resolved_side, shape
    return tuple(node for node in drawings if not compact or node.scalar('Enabled') in (True, 'Y'))
