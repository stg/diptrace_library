"""XML symbol content shared by families, with explicit output keys."""
from .xml import set_attribute
from .conversion import warn
from .xml_footprint_vocabulary import HORZ, VERT
from .xml_library_output import project_category
from .xml_output import enum_text, field, numeric, stroke_width, point_attributes
from .xml_font_output import project_size
from .model import Element
from .xml_symbol_vocabulary import (PART_TYPES, SYMBOL_TYPES, PIN_TYPES, ELECTRIC_TYPES,
                                    DRAWING_TYPES, TEXT_SHOW, SPICE_TYPES, SHOW)


def project_symbol_pin(pin, *, units, pad_id, group=-1, fractional_font=True, physical_font_width=True):
    result = Element('Pin')
    point_attributes(result, *pin.arguments[1:3], units)
    set_attribute(result, 'Locked', pin.scalar('Locked'))
    for public, own, labels in (('Type', 'Type', PIN_TYPES), ('ElectricType', 'ElectricType', ELECTRIC_TYPES)):
        set_attribute(result, public, enum_text(pin.scalar(own), labels))
    orientation = pin.scalar('Orientation')
    set_attribute(result, 'Orientation', orientation*90 if 0 <= orientation <= 3 else orientation)
    set_attribute(result, 'PadId', pad_id)
    set_attribute(result, 'Length', numeric(units.length(pin.one('Length').arguments[0])))
    set_attribute(result, 'ShowName', pin.scalar('ShowName'))
    for prefix, own in (('Num', 'PinNum'), ('Name', 'PinName')):
        point_attributes(result, pin.one(own+'XShift').arguments[0], pin.one(own+'YShift').arguments[0],
                         units, names=(prefix+'XShift', prefix+'YShift'))
    set_attribute(result, 'SignalDelay', numeric(pin.scalar('SignalDelay', 0)))
    for public, own in (('NumOrientation', 'PinNumRotate'), ('NameOrientation', 'PinNameRotate')):
        set_attribute(result, public, pin.scalar(own))
    if group >= 0:
        set_attribute(result, 'Group', group)
    for public, own in (('SpiceSignal', 'ModelSig'), ('Name', 'Name'), ('PadNumber', 'StringNumber')):
        if pin.scalar(own):
            field(result, public, pin.scalar(own))
    font = result.add('NameFont')
    for public, own in (('Size', 'NameFontSize'), ('Width', 'NameFontWidth'), ('Scale', 'NameFontScale')):
        set_attribute(font, public, stroke_width(pin.one(own).arguments[0],units)
                      if own == 'NameFontWidth' and physical_font_width else pin.one(own).arguments[0])
    project_size(pin, font, size='NameFontSize', legacy='Size', mono='NameFontMono', fractional=fractional_font)
    return result


def project_symbol_drawing(shape, *, units, group=-1, fractional_font=True, physical_font_width=True):
    result = Element('Shape')
    kind = shape.scalar('Type')
    set_attribute(result, 'Type', enum_text(kind, DRAWING_TYPES))
    if kind != 10:
        set_attribute(result, 'LineWidth', numeric(units.length(shape.one('PenWidth').arguments[0])))
    set_attribute(result, 'Locked', shape.scalar('Locked'))
    if kind == 10:
        for public, own in (('FontVector', 'VectorFont'), ('FontSize', 'FontSize'), ('FontWidth', 'FontWidth'),
                            ('FontScale', 'FontScale'), ('FontColor', 'FontColor'), ('LineSpacing', 'LineSpacing')):
            set_attribute(result, public, stroke_width(shape.one(own).arguments[0],units)
                          if own == 'FontWidth' and physical_font_width else shape.one(own).arguments[0])
        set_attribute(result, 'TextShow', enum_text(shape.scalar('FontType'), TEXT_SHOW))
        project_size(shape, result, fractional=fractional_font)
        if shape.scalar('FontName'):
            set_attribute(result, 'FontName', shape.scalar('FontName'))
        set_attribute(result, 'Angle', shape.one('TextAngle').arguments[0])
        for public, own, labels in (('HorzAlign', 'TextHorz', HORZ), ('VertAlign', 'TextVert', VERT),
                                    ('TextAlign', 'TextAlign', HORZ)):
            set_attribute(result, public, enum_text(shape.scalar(own), labels, negative=labels[-1]))
    if group >= 0:
        set_attribute(result, 'Group', group)
    if kind == 10 and shape.select('TextLine/pt'):
        lines = result.add('Lines')
        for line in shape.select('TextLine/pt'):
            field(lines, 'Item', line.arguments[0])
    points = shape.select('Points_New/pt')
    if points:
        target = result.add('Points')
        for point in points:
            point_attributes(target.add('Item'), *point.arguments, units)
    return result


def project_symbol(part, *, units, destination, pins=(), drawings=(), groups=(), connections=(),
                   pattern_style=None, datasheet='', report=None):
    """Serialize content selected by the owning family adapter.

    Groups are (key, x, y) tuples; connections are public pad-key pairs.
    Supplied XML records belong to the detached output view.
    """
    if any(part.get('Verification', (False,)*7)):
        warn(report, 'symbol-verification', destination,
             'XML omits saved symbol verification states', (part,),
             recoverability='the symbol definition remains; verification states default to false on import')
    flagged = tuple(shape for shape in part.select('Shapes/Shape')
                    if shape.scalar('Enabled') and
                    (shape.scalar('ShowPart', False) or shape.scalar('MarkingGenerated', False)))
    if flagged:
        warn(report, 'cached-drawing-flags', destination,
             'XML omits cached symbol visibility and generation flags', flagged,
             recoverability='drawing geometry and text remain; these flags default to false on import')
    result = Element('Part')
    if part.values[1]:
        set_attribute(result, 'RefDes', part.arguments[1])
    set_attribute(result, 'PartType', enum_text(part.scalar('PartType'), PART_TYPES))
    if part.scalar('ShowNumbers') > 0:
        set_attribute(result, 'ShowNumbers', enum_text(part.scalar('ShowNumbers'), SHOW))
    set_attribute(result, 'Type', enum_text(part.scalar('Type'), SYMBOL_TYPES))
    for public, own in (('Int1', 'Number1'), ('Int2', 'Number2')):
        set_attribute(result, public, part.scalar(own))
    for name in ('Width', 'Height'):
        set_attribute(result, name, numeric(units.length(part.one(name).arguments[0])))
    set_attribute(result, 'LockTypeChange', part.scalar('LockProperties'))
    if part.scalar('SubfolderIndex', -1) >= 0:
        set_attribute(result, 'SubFolderIndex', part.scalar('SubfolderIndex'))
    if part.values[0]:
        field(result, 'Name', part.arguments[0])
    field(result, 'PartName', part.scalar('PartName'))
    if part.scalar('Value'):
        field(result, 'Value', part.scalar('Value'))
    point_attributes(result.add('Origin'), part.one('Origin_X').arguments[0], part.one('Origin_Y').arguments[0], units)
    datasheet = part.scalar('Datasheet', datasheet)
    if datasheet:
        field(result, 'Datasheet', datasheet)
    model = result.add('SpiceModel')
    set_attribute(model, 'Type', enum_text(part.scalar('ModelType'), SPICE_TYPES))
    if part.scalar('ModelString'):
        field(model, 'Model', part.scalar('ModelString'))
    if part.select('ModelBody/Line'):
        details = model.add('Details')
        for line in part.select('ModelBody/Line'):
            field(details, 'Item', line.arguments[0])
    if part.scalar('Manufacturer'):
        field(result, 'Manufacturer', part.scalar('Manufacturer'))
    category = project_category(part)
    if category is not None:
        result.append(category)
    suppliers = part.child('Suppliers')
    fields = ('PartNumber', 'Manufacturer', 'Pattern', 'Supplier', 'Currency')
    if suppliers is not None and any(suppliers.scalar(name) for name in fields):
        target = result.add('Suppliers')
        for name in fields:
            if suppliers.scalar(name):
                field(target, name, suppliers.scalar(name))
    target = result.add('Pins')
    for pin in pins:
        target.append(pin)
    target = result.add('Shapes')
    for drawing in drawings:
        target.append(drawing)
    groups = tuple(groups)
    if groups:
        target = result.add('Groups')
        for key, x, y in groups:
            item = target.add('Item')
            set_attribute(item, 'Id', key)
            point_attributes(item, x, y, units)
    users = part.select('UserFields/UserField')
    if users:
        target = result.add('AddFields')
        for user in users:
            item = target.add('AddField')
            set_attribute(item, 'Type', enum_text(user.values[2], ('Text', 'Link')))
            field(item, 'Name', user.arguments[0])
            field(item, 'Text', user.arguments[1])
    if pattern_style is not None:
        set_attribute(result.add('Pattern'), 'Style', pattern_style)
    connections = tuple(connections)
    if connections:
        target = result.add('InternalConnections')
        for first, second in connections:
            item = target.add('IntCon')
            set_attribute(item, 'X', first)
            set_attribute(item, 'Y', second)
    return result
