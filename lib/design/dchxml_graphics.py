"""Public XML schematic drawings from current geometry and display data."""
from .dchxml import set_attribute
from .dchxml_components import HORZ, VERT
from .dchxml_settings import enum_text, field, numeric
from .dchxml_symbols import point_attributes
from .model import Element


DRAWING_TYPES = ('None', 'Line', 'Arc', 'Arrow', 'Rectangle', 'FillRect', 'Obround', 'FillObround',
                 'Polyline', 'Polygon', 'Text', 'Picture')


def project_drawing(shape, *, index, units):
    result = Element('Shape')
    kind = shape.scalar('Type')
    set_attribute(result, 'Id', index)
    set_attribute(result, 'Type', enum_text(kind, DRAWING_TYPES))
    set_attribute(result, 'Sheet', shape.scalar('Page'))
    if kind not in (10, 11):
        width = shape.one('PenWidth').arguments[0]
        if width.value > -1:
            set_attribute(result, 'LineWidth', numeric(units.length(width)))
        set_attribute(result, 'Color', shape.scalar('Color'))
    if kind == 10:
        for public, own in (('NetId', 'RelatedNet'), ('BusId', 'RelatedBus')):
            if shape.scalar(own) >= 0:
                set_attribute(result, public, shape.scalar(own))
    if kind in (10, 11):
        set_attribute(result, 'Angle', shape.one('TextAngle').arguments[0])
        if kind == 11:
            for public, own in (('PictureWidth', 'Picture_Width'), ('PictureHeight', 'Picture_Height')):
                set_attribute(result, public, numeric(units.length(shape.one(own).arguments[0])))
            set_attribute(result, 'PictureProportions', shape.scalar('Picture_Proportions'))
        for public, own, labels in (('HorzAlign', 'TextHorz', HORZ), ('VertAlign', 'TextVert', VERT)):
            set_attribute(result, public, enum_text(shape.scalar(own), labels, negative=labels[-1]))
        if kind == 11:
            set_attribute(result, 'PictureTransparent', shape.one('Picture_Transparent').arguments[0])
        else:
            set_attribute(result, 'TextAlign', enum_text(shape.scalar('TextAlign'), HORZ, negative=HORZ[-1]))
            for public, own in (('FontVector', 'VectorFont'), ('FontSize', 'FontSize'), ('FontWidth', 'FontWidth'),
                                ('FontScale', 'FontScale'), ('FontColor', 'FontColor'), ('LineSpacing', 'LineSpacing')):
                set_attribute(result, public, shape.one(own).arguments[0])
    if shape.scalar('Group') >= 0:
        set_attribute(result, 'Group', shape.scalar('Group'))
    for name in ('Selected', 'Locked'):
        if shape.scalar(name):
            set_attribute(result, name, True)
    points = shape.select('Points_New/pt')
    if points:
        target = result.add('Points')
        for point in points:
            point_attributes(target.add('Point'), *point.arguments, units)
    if kind == 10:
        field(result, 'FontName', shape.scalar('FontName'))
        lines = shape.select('TextLine/pt')
        if lines:
            target = result.add('TextLines')
            for line in lines:
                field(target, 'TextLine', line.arguments[0])
    if kind == 11:
        path = shape.scalar('Picture_File')
        variable = shape.scalar('Picture_File_Variable', '')
        if not variable.replace(' ', ''):
            variable = path
        target = result.add('PictureFile')
        field(target, 'Path', path)
        field(target, 'Var', variable)
    return result


def project_drawings(schematic, *, units):
    result = Element('Shapes')
    for index, drawing in enumerate(schematic.select('Shapes/Shape')):
        if drawing.scalar('Enabled'):
            result.append(project_drawing(drawing, index=index, units=units))
    return result
