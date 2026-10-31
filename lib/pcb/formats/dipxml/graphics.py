"""Public board outline, groups and drawings into current PCB geometry."""
from decimal import Decimal

from ....common.xml_records import enum_value, length, point
from ....common.xml_library_values import read_path, read_points
from ....common.xml_footprint_vocabulary import HORZ, VERT
from ....common.xml_font_import import read_font, read_text_extent
from ..assembly.graphic_inputs import DrawingInput
from ..errors import PcbError
from .keys import position, unique_id
from .font import read_width


LAYERS = ('Top Assy', 'Top Silk', 'Route Keepout', 'Signal/Plane', 'Bottom Silk', 'Bottom Assy',
          'Top Mask', 'Top Paste', 'Bottom Paste', 'Bottom Mask', 'Board Cutout', 'Placement Keepout',
          'None', 'Top Dimension', 'Bottom Dimension', 'Non-Signal', 'Top Courtyard', 'Bottom Courtyard',
          'Top Outline', 'Bottom Outline', 'Top Terminals', 'Bottom Terminals')
TYPES = ('Line', 'Arc', 'Rectangle', 'FillRect', 'Obround', 'FillObround', 'Text', 'Picture', 'Polyline', 'Polygon')


def _fields(owner, **values):
    for name, value in values.items():
        owner.add(name, value)


def read_outline(record, board, *, units):
    source = record.take('BoardOutline')
    points = board.add('Points')
    if source is None:
        return
    for name, default in (('Enabled', True), ('Selected', False), ('Locked', False), ('PanelExclude', False)):
        board.add(name, source.boolean(name, default))
    board.add('ShieldGroup', source.integer('ShieldGroup', -1))
    for row in source.rows('Points', 'Point'):
        points.add('pt', *point(row, units), row.boolean('Arc', False))
        row.finish()
    source.finish()


def read_groups(record, board):
    groups, seen = board.add('Groups'), {}
    for source in record.rows('Groups', 'Group'):
        key = unique_id(source, seen, label='board group')
        group = groups.add('Group', key, 0, 0)
        _fields(group, Enabled=source.boolean('Enabled', True), Selected=source.boolean('Selected', False))
        seen[key] = group
        source.finish()


def read_non_signals(record, board):
    collection, by_key = board.add('NonSignals'), {}
    for index, source in enumerate(record.rows('NonSignals', 'NonSignal')):
        key = source.integer('Id', index)
        if key < 0:
            key = index
        if key in by_key:
            raise PcbError(f'{source.node.path}: duplicate non-signal layer Id {key}')
        layer = collection.add('NonSignal', source.text('Name', ''), source.integer('Color', 0x8A8A8A), key,
                               enum_value(source.value('Side', 'None'), ('None', 'Top', 'Bottom')))
        by_key[key] = layer
        source.finish()
    return by_key


def _layer_selector(value, layers, *, path, label):
    try:
        key = enum_value(value, ())
    except ValueError:
        matches = [layer for layer in layers.values() if layer.values[0] == value.value]
        if len(matches) != 1:
            raise PcbError(f'{path}: unavailable or ambiguous {label} name {value.value!r}') from None
        return matches[0]._ordinal()
    return position(key, layers, label=label, path=path)


def _vector(source, shape, *, units):
    record = source.take('PictureVector')
    if record is None:
        return
    vector = shape.add('PictureVector')
    _fields(vector, Width=length(record.number('Width', 0), units),
            Height=length(record.number('Height', 0), units))
    polygons = vector.add('Polygons')
    for polygon in record.rows('Polygons', 'Polygon'):
        output = polygons.add('Polygon')
        points = output.add('Points')
        for index, vertex in enumerate(polygon.rows('Points', ('Item', 'Point'))):
            node = points.add('Item', index)
            _fields(node, **dict(zip(('X', 'Y'), point(vertex, units))))
            vertex.finish()
        polygon.finish()
    record.finish()


def read_drawings(record, board, *, units, layers, non_signals, version):
    collection, seen, prepared = board.add('Shapes'), {}, []
    for index, source in enumerate(record.rows('Shapes', 'Shape')):
        key = unique_id(source, seen, label='board drawing')
        shape = collection.add('Shape', index)
        seen[key] = shape
        family = enum_value(source.value('Layer', LAYERS[0]), LAYERS)
        supplied_layer = source.has('LayId')
        selector = source.value('LayId', 0)
        if family in (3, 15):
            layer = _layer_selector(selector, layers if family == 3 else non_signals,
                                    path=source.node.path, label='drawing layer') if supplied_layer else 0
        else:
            layer = enum_value(selector, ())
        _fields(shape, Layer=family, LayId=layer, Type=enum_value(source.value('Type', TYPES[0]), TYPES),
                Group=source.integer('Group', -1), NetNumber=source.integer('NetId', -1),
                Color=-1, BrushColor=-1, FontColor=-1, FontName=source.text('FontName', 'Tahoma'),
                PenWidth=length(source.number('LineWidth'), units) if source.has('LineWidth') else -1,
                TextAngle=source.number('Angle', 0), LineSpacing=source.number('LineSpacing', Decimal('1.2')),
                FontScale=source.number('FontScale', 1), ShieldGroup=-1,
                PictureTransparent=source.number('PictureTransparent', 0), Picture_File='', Picture_File_Variable='')
        shape.add('FontWidth', read_width(source, units=units, version=version))
        for name, default in (('Enabled', True), ('Selected', False), ('AllLayers', False), ('Locked', False),
                              ('PanelExclude', False), ('Inverted', False), ('PictureRaster', False),
                              ('PictureProportions', True), ('PictureFlipped', False)):
            shape.add(name, source.boolean(name, default))
        shape.add('VectorFont', source.boolean('FontVector', True))
        read_font(source, shape, default=1)
        read_text_extent(source)
        for public, own, labels in (('HorzAlign', 'TextHorz', HORZ), ('VertAlign', 'TextVert', VERT),
                                    ('TextAlign', 'TextAlign', HORZ)):
            shape.add(own, enum_value(source.value(public), labels, negative=labels[-1])
                      if source.has(public) else -1)
        for name in ('PictureWidth', 'PictureHeight'):
            shape.add(name, length(source.number(name, 0), units))
        filename = source.take('PictureFile')
        if filename is not None:
            actual, variable = read_path(filename)
            shape.set_field('Picture_File', actual)
            shape.set_field('Picture_File_Variable', variable)
        points = shape.add('Points')
        for row in read_points(source, units=units):
            points.append(row)
        text = shape.add('TextLine')
        for row in source.rows('TextLines', 'TextLine'):
            value = row.content()
            if value.kind != 'string':
                raise PcbError(f'{row.node.path}: expected drawing text')
            text.add('pt', value)
            row.finish(allow_text=True)
        _vector(source, shape, units=units)
        source.finish()
        prepared.append(DrawingInput(shape, key))
    return tuple(prepared)
