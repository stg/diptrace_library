"""Public symbol definitions into own pins, drawings and symbol data."""
from .components import (HORZ, VERT)
from .import_library_values import (read_points, read_groups, mapped_group, read_category, read_user_fields)
from .import_values import (enum_value, length, point, replace_rows)
from .settings import (SHOW)
from .symbols import (PART_TYPES, SYMBOL_TYPES, PIN_TYPES, ELECTRIC_TYPES, DRAWING_TYPES, TEXT_SHOW, SPICE_TYPES)
from ....common.model import (Element)
from ...model.objects import (new_symbol, new_symbol_shape, new_pin)
from .fonts import (read_font, read_text_extent)


def read_symbol_pin(record, *, index, units, groups):
    record.integer('Id', index)
    pin = new_pin(index, placed=False)
    pin.set_values(index, *point(record, units))
    for public, own, labels in (('Type', 'Type', PIN_TYPES), ('ElectricType', 'ElectricType', ELECTRIC_TYPES)):
        pin.set_field(own, enum_value(record.value(public, labels[0]), labels))
    pin.set_field('Orientation', enum_value(record.number('Orientation', 0), ('0', '90', '180', '270')))
    pin.set_field('Number', record.integer('PadId', -1))
    pin.set_field('Locked', record.boolean('Locked', False))
    pin.set_field('Length', length(record.number('Length', 0), units))
    pin.set_field('ShowName', record.boolean('ShowName', True))
    for prefix, own in (('Num', 'PinNum'), ('Name', 'PinName')):
        for axis, value in zip(('X', 'Y'), point(record, units, (prefix+'XShift', prefix+'YShift'), 0)):
            pin.set_field(own+axis+'Shift', value)
    delay = pin.add('SignalDelay', record.number('SignalDelay', 0))
    if not delay.values[0]:
        delay.annotations['asc_omit'] = 'not present in cached schematic ASC/DCH'
    for public, own in (('NumOrientation', 'PinNumRotate'), ('NameOrientation', 'PinNameRotate')):
        pin.set_field(own, record.integer(public, 0))
    pin.set_field('Group', mapped_group(record, groups, pin))
    for public, own in (('SpiceSignal', 'ModelSig'), ('Name', 'Name'), ('PadNumber', 'StringNumber')):
        pin.set_field(own, record.text(public, ''))
    font = record.take('NameFont')
    if font is not None:
        read_font(font, pin, size='NameFontSize', legacy='Size', prefix='Name')
        for public, own, default in (('Width', 'NameFontWidth', -1), ('Scale', 'NameFontScale', 1)):
            pin.set_field(own, font.number(public, default))
        font.finish()
    record.finish()
    return pin


def read_symbol_drawing(record, *, index, units, groups):
    record.integer('Id', index)
    shape = new_symbol_shape(index)
    kind = enum_value(record.value('Type', 'Undefined'), DRAWING_TYPES)
    shape.set_field('Type', kind)
    shape.set_field('Locked', record.boolean('Locked', False))
    shape.set_field('PenWidth', length(record.number('LineWidth', 0), units))
    shape.set_field('Group', mapped_group(record, groups, shape))
    if kind == 10:
        shape.set_field('VectorFont', record.boolean('FontVector', True))
        for public, own, default in (('FontSize', 'FontSize', 6), ('FontWidth', 'FontWidth', -1),
                                    ('FontScale', 'FontScale', 1), ('LineSpacing', 'LineSpacing', 1.2), ('Angle', 'TextAngle', 0)):
            shape.set_field(own, record.number(public, default))
        shape.set_field('FontColor', record.integer('FontColor', 0))
        shape.set_field('FontType', enum_value(record.value('TextShow', 'Any Text'), TEXT_SHOW))
        shape.set_field('FontName', record.text('FontName', ''))
        for public, own, labels in (('HorzAlign', 'TextHorz', HORZ), ('VertAlign', 'TextVert', VERT),
                                    ('TextAlign', 'TextAlign', HORZ)):
            shape.set_field(own, enum_value(record.value(public, labels[0]), labels, negative=labels[-1]))
        lines = shape.one('TextLine')
        for item in record.rows(('Lines', 'TextLines'), ('Item', 'TextLine')):
            lines.add('pt', item.content())
            item.finish(allow_text=True)
        shape.set_field('Name', lines.children()[0].arguments[0] if lines.children() else '')
        read_font(record, shape)
        read_text_extent(record)
    replace_rows(shape, 'Points_New', read_points(record, units=units))
    record.finish()
    return shape


def read_symbol(record, *, units):
    if record.has('Id'):
        record.integer('Id')
    part = new_symbol(record.text('Name', ''), record.text('RefDes', ''), placed=False)
    for public, own, labels in (('PartType', 'PartType', PART_TYPES), ('Type', 'Type', SYMBOL_TYPES),
                                ('ShowNumbers', 'ShowNumbers', SHOW)):
        part.set_field(own, enum_value(record.value(public, labels[0]), labels))
    for public, own in (('Int1', 'Number1'), ('Int2', 'Number2')):
        part.set_field(own, record.integer(public, 0))
    for name in ('Width', 'Height'):
        part.set_field(name, length(record.number(name, 0), units))
    part.set_field('LockProperties', record.boolean('LockTypeChange', False))
    for name in ('PartName', 'Value', 'Manufacturer'):
        part.set_field(name, record.text(name, ''))
    datasheet = part.add('Datasheet', record.text('Datasheet', ''))
    if not datasheet.values[0]:
        datasheet.annotations['asc_omit'] = 'not present in cached schematic ASC/DCH'
    origin = record.take('Origin')
    if origin is not None:
        for name, value in zip(('Origin_X', 'Origin_Y'), point(origin, units, default=0)):
            part.set_field(name, value)
        origin.finish()
    model = record.take('SpiceModel')
    if model is not None:
        part.set_field('ModelType', enum_value(model.value('Type', 'SubCkt'), SPICE_TYPES))
        part.set_field('ModelString', model.text('Model', ''))
        for line in model.rows('Details', 'Item'):
            part.one('ModelBody').add('Line', line.content())
            line.finish(allow_text=True)
        model.finish()
    read_category(record.take('Category'), part)
    supplier = record.take('Suppliers')
    if supplier is not None:
        for name in ('PartNumber', 'Manufacturer', 'Pattern', 'Supplier', 'Currency'):
            part.one('Suppliers').set_field(name, supplier.text(name, ''))
        supplier.finish()
    groups = read_groups(record, part, units=units)
    for index, source in enumerate(record.rows('Pins', 'Pin')):
        part.one('Pins').append(read_symbol_pin(source, index=index, units=units, groups=groups))
    for index, source in enumerate(record.rows('Shapes', 'Shape')):
        part.one('Shapes').append(read_symbol_drawing(source, index=index, units=units, groups=groups))
    read_user_fields(record, part)
    pattern = record.take('Pattern')
    pattern_style = None
    if pattern is not None:
        pattern_style = pattern.text('Style')
        pattern.finish()
    connections = []
    for source in record.rows('InternalConnections', 'IntCon'):
        connections.append(Element('IntCon', source.integer('X'), source.integer('Y')))
        source.finish()
    record.finish()
    return part, pattern_style, connections
