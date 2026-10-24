"""Public XML symbol definitions, pins and drawings from owned design records."""
from .dchxml import set_attribute
from .dchxml_components import HORZ, VERT, _category
from .dchxml_settings import SHOW, enum_text, field, numeric
from .model import Element
from .pad_keys import project_pad_id
from .local_keys import project_key, public_keys, reserved_keys


PART_TYPES = ('Normal', 'Power', 'Net Port', 'Hierarchy Connector', 'Hierarchy Block')
SYMBOL_TYPES = ('Free', '2 Sides', 'IC-2 Sides', 'IC-4 Sides')
PIN_TYPES = ('Default', 'Dot', 'Polarity In', 'Polarity Out', 'Non Logic', 'Open', 'Open High',
             'Open Low', '3 State', 'Hysteresis', 'Amplifier', 'Postponed', 'Shift', 'Clock', 'Generator')
ELECTRIC_TYPES = ('Undefined', 'Passive', 'Input', 'Output', 'Bidirectional', 'Open High', 'Open Low',
                  'Passive High', 'Passive Low', '3 State', 'Power')
DRAWING_TYPES = ('Undefined', 'Line', 'Arc', 'Arrow', 'Rectangle', 'FillRect', 'Obround', 'FillObround',
                 'Polyline', 'Polygon', 'Text')
TEXT_SHOW = ('Any Text', 'Name', 'RefDes', 'Value', 'Part Name', 'Manufacturer', 'Datasheet')
SPICE_TYPES = ('SubCkt', 'Resistor', 'Capacitor', 'Inductor', 'Diode', 'BJT', 'JFET', 'MOSFET',
    'Ga As Transistor', 'Current Source', 'Voltage Source', 'Voltage Dependent Current Source',
    'Voltage Dependent Voltage Source', 'Current Dependent Current Source', 'Current Dependent Voltage Source',
    'Arbitrary Behavioral Source', 'Mutual Inductance', 'Transmission Line', 'Lossy Transmission Line',
    'Single Lossy Transmission Line (TXL)', 'Coupled Multiconductor Line (CPL)', 'Voltage-Controlled Switch',
    'Current-Controlled Switch', 'Uniformly Distributed RC Line')


def point_attributes(target, x, y, units, names=('X', 'Y')):
    for name, value in zip(names, units.point(x, y)):
        set_attribute(target, name, numeric(value))


def project_symbol_pin(pin, *, units, pad_keys=None, group_keys=None, version=46):
    result = Element('Pin')
    point_attributes(result, *pin.arguments[1:3], units)
    set_attribute(result, 'Locked', pin.scalar('Locked'))
    for public, own, labels in (('Type', 'Type', PIN_TYPES), ('ElectricType', 'ElectricType', ELECTRIC_TYPES)):
        set_attribute(result, public, enum_text(pin.scalar(own), labels))
    orientation = pin.scalar('Orientation')
    set_attribute(result, 'Orientation', orientation*90 if 0 <= orientation <= 3 else orientation)
    set_attribute(result, 'PadId', project_pad_id(pin, pad_keys))
    set_attribute(result, 'Length', numeric(units.length(pin.one('Length').arguments[0])))
    set_attribute(result, 'ShowName', pin.scalar('ShowName'))
    for prefix, own in (('Num', 'PinNum'), ('Name', 'PinName')):
        point_attributes(result, pin.one(own+'XShift').arguments[0], pin.one(own+'YShift').arguments[0],
                         units, names=(prefix+'XShift', prefix+'YShift'))
    set_attribute(result, 'SignalDelay', numeric(pin.scalar('SignalDelay', 0)))
    for public, own in (('NumOrientation', 'PinNumRotate'), ('NameOrientation', 'PinNameRotate')):
        set_attribute(result, public, pin.scalar(own))
    group = project_key(pin, 'Group', pin.scalar('Group'), group_keys)
    if group >= 0:
        set_attribute(result, 'Group', group)
    for public, own in (('SpiceSignal', 'ModelSig'), ('Name', 'Name'), ('PadNumber', 'StringNumber')):
        if pin.scalar(own):
            field(result, public, pin.scalar(own))
    font = result.add('NameFont')
    for public, own in (('Size', 'NameFontSize'), ('Width', 'NameFontWidth'), ('Scale', 'NameFontScale')):
        set_attribute(font, public, pin.one(own).arguments[0])
    from .dchxml_fonts import project_size
    project_size(pin, font, size='NameFontSize', legacy='Size', mono='NameFontMono', version=version)
    return result


def project_symbol_drawing(shape, *, units, group_keys=None, version=46):
    result = Element('Shape')
    kind = shape.scalar('Type')
    set_attribute(result, 'Type', enum_text(kind, DRAWING_TYPES))
    if kind != 10:
        set_attribute(result, 'LineWidth', numeric(units.length(shape.one('PenWidth').arguments[0])))
    set_attribute(result, 'Locked', shape.scalar('Locked'))
    if kind == 10:
        for public, own in (('FontVector', 'VectorFont'), ('FontSize', 'FontSize'), ('FontWidth', 'FontWidth'),
                            ('FontScale', 'FontScale'), ('FontColor', 'FontColor'), ('LineSpacing', 'LineSpacing')):
            set_attribute(result, public, shape.one(own).arguments[0])
        set_attribute(result, 'TextShow', enum_text(shape.scalar('FontType'), TEXT_SHOW))
        from .dchxml_fonts import project_size
        project_size(shape, result, version=version)
        if shape.scalar('FontName'):
            set_attribute(result, 'FontName', shape.scalar('FontName'))
        set_attribute(result, 'Angle', shape.one('TextAngle').arguments[0])
        for public, own, labels in (('HorzAlign', 'TextHorz', HORZ), ('VertAlign', 'TextVert', VERT),
                                    ('TextAlign', 'TextAlign', HORZ)):
            set_attribute(result, public, enum_text(shape.scalar(own), labels, negative=labels[-1]))
    group = project_key(shape, 'Group', shape.scalar('Group'), group_keys)
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


def project_symbol(part, *, units, pattern=None, pattern_style=None, datasheet='', pad_keys=None, version=46):
    """Project an unplaced definition; no instance geometry is inferred here."""
    result = Element('Part')
    group_keys = public_keys(part.select('Groups/pt'), reserved_keys(
        [*part.select('Pins/Pin'), *part.select('Shapes/Shape')], ('Group',)))
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
    category = _category(part)
    if category is not None:
        result.append(category)
    suppliers = part.child('Suppliers')
    fields = ('PartNumber', 'Manufacturer', 'Pattern', 'Supplier', 'Currency')
    if suppliers is not None and any(suppliers.scalar(name) for name in fields):
        target = result.add('Suppliers')
        for name in fields:
            if suppliers.scalar(name):
                field(target, name, suppliers.scalar(name))
    pins = result.add('Pins')
    for pin in part.select('Pins/Pin'):
        if pin.scalar('Enabled'):
            pins.append(project_symbol_pin(pin, units=units, pad_keys=pad_keys, group_keys=group_keys, version=version))
    shapes = result.add('Shapes')
    for shape in part.select('Shapes/Shape'):
        if shape.scalar('Enabled') and not shape.scalar('MarkingGenerated', False):
            shapes.append(project_symbol_drawing(shape, units=units, group_keys=group_keys, version=version))
    groups = part.select('Groups/pt')
    if groups:
        target = result.add('Groups')
        for index, group in enumerate(groups):
            if group.values[0]:
                item = target.add('Item')
                set_attribute(item, 'Id', group_keys[index])
                point_attributes(item, *group.arguments[-2:], units)
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
    connections = pattern.select('InternalConnections/IntCon') if pattern is not None else []
    if connections:
        target = result.add('InternalConnections')
        for connection in connections:
            item = target.add('IntCon')
            for name, value in zip(('X', 'Y'), connection.arguments):
                number = value.value
                set_attribute(item, name, project_key(connection, name, number, pad_keys))
    return result
