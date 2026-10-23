"""Instantiate public symbol data using owned geometry and explicit overrides."""
import math

from .dchxml_components import HORZ, VERT
from .dchxml_import_library_values import read_category, read_path
from .dchxml_import_values import enum_value, length, point, replace_rows
from .dchxml_settings import SHOW, ALIGN
from .model import Element, Value
from .schematic_objects import new_symbol, new_pin
from .local_keys import copy_missing_keys


def marking(record, *, units, named=False):
    values = [enum_value(record.value('Show', 'Common'), SHOW)]
    if named:
        values.append(enum_value(record.value('ShowPart', 'Common'), SHOW))
    for name, labels in (('Align', ALIGN), ('Horz', HORZ), ('Vert', VERT)):
        values.append(enum_value(record.value(name, labels[0]), labels,
                                 negative=labels[-1] if name in ('Horz', 'Vert') else None))
    values.extend(point(record, units, default=0))
    values.append(record.number('Angle', 0))
    return values


def _placement(angle):
    """Resolve discrete placement without an iterative rotation loop.

    Small and negative angles keep their literal placement value. Positive
    angles select the first quarter orientation beyond the normalized target.
    Some targets have no such orientation; reject that nonterminating state.
    """
    value = float(angle.value)
    if not math.isfinite(value):
        raise ValueError('XML component placement requires a finite angle')
    if value <= .0001:
        return 0, math.degrees(value), value
    normalized = math.fmod(value, math.tau)
    if normalized > math.tau-1e-7:
        normalized -= math.tau
    for turns in range(4):
        radians = turns*math.pi/2
        if radians > normalized-.0001:
            return turns, turns*90, radians
    raise ValueError('XML component angle has no terminating discrete placement')


def _place_geometry(part, turns):
    if not turns:
        return
    quarter = (-turns) % 4

    def rotate(x, y):
        return ((x, y), (-y, x), (-x, -y), (y, -x))[quarter]

    if quarter % 2:
        width, height = part.scalar('Width'), part.scalar('Height')
        part.set_field('Width', height)
        part.set_field('Height', width)
    x, y = rotate(part.scalar('Origin_X'), part.scalar('Origin_Y'))
    part.set_field('Origin_X', x)
    part.set_field('Origin_Y', y)
    for pin in part.select('Pins/Pin'):
        pin.set_values(pin.arguments[0], *rotate(*pin.values[1:3]))
        pin.set_field('Orientation', (pin.scalar('Orientation')-turns) % 4)
    for shape in part.select('Shapes/Shape'):
        points = shape.select('Points_New/pt')
        for position in points:
            position.set_values(*rotate(*position.values))
        if shape.scalar('Type') in (4, 5, 6, 7) and len(points) == 2:
            a, b = points[0].values, points[1].values
            points[0].set_values(min(a[0], b[0]), min(a[1], b[1]))
            points[1].set_values(max(a[0], b[0]), max(a[1], b[1]))
        shape.set_field('TextAngle', (float(shape.scalar('TextAngle'))+turns*math.pi/2) % math.tau)


def read_component(record, definition, pattern, *, units, sheets):
    """Copy our typed definition data, then apply the public instance fields.

    Flips are recorded state. XML definitions already contain their flipped
    geometry; the XML loader applies only quarter-turn placement here.
    """
    part = new_symbol(record.text('Name', definition.values[0]), record.text('RefDes', ''))
    for name in ('PartType', 'Type', 'Number1', 'Number2', 'Width', 'Height', 'LockProperties',
                 'Origin_X', 'Origin_Y', 'ModelType', 'ModelString', 'Manufacturer'):
        part.set_field(name, *definition.one(name).arguments)
    part.set_field('Datasheet', definition.scalar('Datasheet', ''))
    part.set_field('BaseName', definition.values[0])
    part.set_field('BaseRefDes', definition.values[1])
    for name in ('PartNumber', 'Manufacturer', 'Pattern', 'Supplier', 'SourceLocator', 'Currency'):
        part.one('Suppliers').set_field(name, definition.one('Suppliers').scalar(name, ''))
    replace_rows(part, 'ModelBody', [line.clone() for line in definition.select('ModelBody/Line')])
    replace_rows(part, 'Shapes', [shape.clone() for shape in definition.select('Shapes/Shape')])
    pins = []
    for index, original in enumerate(definition.select('Pins/Pin')):
        pin = new_pin(index)
        pin.set_values(index, *original.arguments[1:3])
        for field in original.children():
            if field.kind != 'UnresolvedKeys':
                pin.set_field(field.kind, *field.arguments)
        copy_missing_keys(original, pin)
        pins.append(pin)
    replace_rows(part, 'Pins', pins)
    part.one('Pattern').detach()
    part.append(pattern.clone())
    part.set_field('Number', record.integer('Id'))
    part.set_field('HiddenId', record.integer('UpdateId', 0))
    part.set_field('PageHiddenId', record.integer('BlockId', 0))
    sheet = record.integer('Sheet', 0)
    if sheet not in sheets:
        raise ValueError(f'{record.node.path}: unresolved sheet {sheet}')
    part.set_field('Page', sheets[sheet])
    for name, value in zip(('X', 'Y'), point(record, units, default=0)):
        part.set_field(name, value)
    angle = record.number('Angle', 0)
    turns, degrees, _ = _placement(angle)
    part.set_field('Angle', degrees)
    _place_geometry(part, turns)
    for name in ('AllowParts', 'HorzFlip', 'VertFlip', 'ShowOrigin', 'CustomMarkingFont', 'MarkingFontAll', 'Selected', 'Locked'):
        part.set_field(name, record.boolean(name, name == 'AllowParts'))
    part.set_field('PartNumber', record.integer('PartNumber', 0))
    part.set_field('PartName', record.text('PartName', ''))
    part.set_field('PartDescriptor', record.text('PartRefDes', ''))
    part.set_field('Value', record.text('Value', definition.scalar('Value')))
    part.set_field('ShowNumbers', enum_value(record.value('ShowNumbers', SHOW[definition.scalar('ShowNumbers')]
                   if 0 <= definition.scalar('ShowNumbers') < len(SHOW) else str(definition.scalar('ShowNumbers'))), SHOW))
    part.set_field('MarkingFontSize', record.integer('MarkingFontSize', 6))
    part.set_field('Group', record.integer('Group', -1))
    path = record.take('LibPath')
    if path is not None:
        actual, variable = read_path(path)
        part.set_field('LibPath', actual)
        part.set_field('LibPath_Variable', variable)
    for name in ('RefDes', 'Name', 'Value', 'Manufacturer', 'Datasheet'):
        source = record.take(name+'Marking')
        if source is not None:
            part.one('Show'+name).set_values(*marking(source, units=units, named=name in ('RefDes', 'Name')))
            source.finish()
    for source in record.rows('AddFields', 'AddField'):
        kind = enum_value(source.value('Type', 'Text'), ('Text', 'Link'))
        values = marking(source, units=units)
        part.one('UserFields').add('UserField', source.text('Name', ''), source.text('Text', ''), kind, *values)
        source.finish()
    overrides = record.rows('Pins', 'Pin')
    if len(overrides) != len(pins):
        raise ValueError(f'{record.node.path}: instance pin count differs from its symbol definition')
    for source, pin in zip(overrides, pins):
        pin.set_field('NetNumber', source.integer('NetId', -1))
        pin.set_field('NoConnect', source.boolean('NotConnected', False))
        source.finish()
    read_category(record.take('Category'), part)
    record.finish()
    return part
