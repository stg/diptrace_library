"""Shared physical drawing and 3D XML projections, without family policy."""
from decimal import Decimal
from .xml import set_attribute
from .xml_output import enum_text, numeric, field, point_attributes, stroke_width
from .xml_font_output import project_size
from .xml_footprint_vocabulary import DRAWING_TYPES, LAYERS, TEXT_SHOW, HORZ, VERT
from .model import Element


def project_model3d(model, *, units, variable_fallback=True):
    result = Element('Model3D')
    for name in ('Mirror', 'NoSearch'):
        set_attribute(result, name, model.scalar(name))
    set_attribute(result, 'Units', enum_text(model.scalar('Units'), ('mm', 'mil', 'inch', 'Wings'), negative='Wings'))
    point_attributes(result, model.one('IPC_XOff').arguments[0], model.one('IPC_YOff').arguments[0],
                     units, names=('IPC_XOff', 'IPC_YOff'))
    set_attribute(result, 'AutoHeight', numeric(units.length(model.one('AutoHeight').arguments[0])))
    set_attribute(result, 'AutoColor', model.scalar('AutoColor'))
    set_attribute(result, 'Type', enum_text(model.scalar('Type'), ('File', 'IPC-7351', 'Outline')))
    set_attribute(result, 'KeepPins', model.scalar('KeepPins'))
    path = model.scalar('Model3DFile')
    variable = model.scalar('Model3DFile_Variable', '')
    if variable_fallback and not variable.replace(' ', ''):
        variable = path
    if path or variable:
        filename = result.add('Filename')
        field(filename, 'Path', path)
        field(filename, 'Var', variable)
    for name in ('Rotate', 'Offset', 'Zoom'):
        target = result.add(name)
        for axis in ('X', 'Y', 'Z'):
            value = model.one(name+'/'+axis).arguments[0]
            if name == 'Offset':
                value = units.length(value)
                if axis == 'Y':
                    value = value.copy_negate() if isinstance(value,Decimal) else -value
            set_attribute(target, axis, numeric(value))
    return result


def project_drawing(shape, *, index, units, group=-1, pad_id=-1,
                    fractional_font=True, physical_font_width=True):
    """Project physical drawing data; callers supply their resolved local keys."""
    result = Element('Shape')
    kind = shape.scalar('Type')
    for name, value in (('Id', index), ('Type', enum_text(kind,DRAWING_TYPES)),
                        ('Locked',shape.scalar('Locked')), ('Layer',enum_text(shape.scalar('Layer'),LAYERS))):
        set_attribute(result,name,value)
    if kind == 7:
        for public, own in (('FontVector','VectorFont'),('FontName','FontName'),('FontScale','FontScale'),
                            ('LineSpacing','LineSpacing')):
            set_attribute(result,public,shape.one(own).arguments[0])
        width = shape.one('FontWidth').arguments[0]
        set_attribute(result,'FontWidth',stroke_width(width,units) if physical_font_width else width)
        project_size(shape,result,fractional=fractional_font)
        set_attribute(result,'TextShow',enum_text(shape.scalar('TextShow'),TEXT_SHOW))
        set_attribute(result,'Angle',shape.one('TextAngle').arguments[0])
        for public, own, labels in (('HorzAlign','TextHorz',HORZ),('VertAlign','TextVert',VERT),
                                    ('TextAlign','TextAlign',HORZ)):
            set_attribute(result,public,enum_text(shape.scalar(own),labels,negative=labels[-1]))
        if lines := shape.select('TextLine/pt'):
            target = result.add('Lines')
            for line in lines:
                field(target,'Item',line.arguments[0])
    elif (width := shape.one('Width').arguments[0]).value != -1:
        set_attribute(result,'LineWidth',numeric(units.length(width)))
    set_attribute(result,'AllLayers',shape.scalar('AllLayers'))
    for name, key in (('Group',group),('PadId',pad_id)):
        if key >= 0:
            set_attribute(result,name,key)
    if points := shape.select('Points_New/pt'):
        target = result.add('Points')
        for point in points:
            point_attributes(target.add('Item'),*point.arguments,units)
    return result


def project_dimension(dimension, *, units, attachments, group=-1, fractional_font=True,
                      physical_font_width=True, none_label='None',
                      connection_labels=('Pad', 'Shape', 'Hole', 'Terminal'),
                      font_name_attribute=True):
    """Serialize shared local dimension data after family attachment projection."""
    result = Element('Dimension')
    set_attribute(result,'Locked',dimension.scalar('Locked'))
    set_attribute(result,'Type',enum_text(dimension.scalar('Type'),('Horizontal','Vertical','Free','Radius','Pointer')))
    for side, attachment in zip(('1','2'),attachments):
        mode, owner, member, point = attachment
        set_attribute(result,'Connected'+side,enum_text(mode,connection_labels,negative=none_label))
        for name, value in (('Object',owner),('SubObject',member),('Point',point)):
            set_attribute(result,name+side,value)
    set_attribute(result,'Layer',enum_text(dimension.scalar('Layer'),LAYERS))
    for suffix in ('1','2','D'):
        point_attributes(result,dimension.one('X'+suffix).arguments[0],dimension.one('Y'+suffix).arguments[0],
                         units,names=('X'+suffix,'Y'+suffix))
    set_attribute(result,'ArrowSize',numeric(units.length(dimension.one('ArrowSize').arguments[0])))
    set_attribute(result,'Units',enum_text(dimension.scalar('Units'),('Common','inch','mil','mm')))
    for public, own in (('FontVector','VectorFont'),('FontScale','FontScale'),
                        ('ShowUnits','ShowUnits'),('Angle','Angle'),('ExternalRadius','ExternalRadius'),
                        ('PointerMode','PointerMode')):
        set_attribute(result,public,dimension.one(own).arguments[0])
    width = dimension.one('FontWidth').arguments[0]
    set_attribute(result,'FontWidth',stroke_width(width,units) if physical_font_width else width)
    project_size(dimension,result,fractional=fractional_font)
    if group >= 0:
        set_attribute(result,'Group',group)
    if font_name_attribute:
        set_attribute(result,'FontName',dimension.scalar('FontName'))
    else:
        field(result,'FontName',dimension.scalar('FontName'))
    if dimension.scalar('PointerText'):
        field(result,'PointerText',dimension.scalar('PointerText'))
    return result
