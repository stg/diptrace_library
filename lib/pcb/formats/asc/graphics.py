"""Expand ASC board drawings, pour geometry and grouping before shared binding."""
from ....common.model import Element, Value
from ....common.units import square_length
from ....common.picture_sources import picture_reference_index
from ...model import graphic_records
from ..assembly.graphic_inputs import DrawingInput, PourInput
from .values import boolean, booleans, numeric_row, rename
from ..errors import PcbError


def _points(owner, count=2, *, flags=()):
    if owner.values:
        raise PcbError(f'{owner.path}: expected point records')
    for row in owner.children():
        row.set_values(*numeric_row(row, count, flags=flags))


def _key(owner, name, *, default=None):
    rows = owner.children(name)
    if not rows and default is not None:
        return default
    if (len(rows) != 1 or len(rows[0].values) != 1 or rows[0].children()
            or type(rows[0].values[0]) is not int):
        raise PcbError(f'{owner.path}: expected an integer {name}')
    value = rows[0].values[0]
    rows[0].detach()
    return value


def _vector(shape):
    fields = {name: shape.child('Vector_'+name) for name in ('Width', 'Height', 'Polygons')}
    if not any(fields.values()):
        return
    if not all(field is not None for field in fields.values()) or shape.child('PictureVector') is not None:
        raise PcbError(f'{shape.path}: incomplete or duplicate vector picture')
    for name in ('Width', 'Height'):
        node = fields[name]
        if len(node.arguments) != 1 or node.children() or node.arguments[0].kind != 'number' or node.arguments[0].unit:
            raise PcbError(f'{node.path}: expected one vector dimension')
    polygons = fields['Polygons']
    if polygons.values:
        raise PcbError(f'{polygons.path}: expected vector polygons')
    picture = shape.add('PictureVector')
    for name, field in fields.items():
        field.kind = name
        field.move_to(picture)
    for polygon in polygons.children():
        if polygon.kind != 'Vector_Polygon' or polygon.values:
            raise PcbError(f'{polygon.path}: expected a vector polygon')
        polygon.kind = 'Polygon'
        points = polygon.one('Points')
        _points(points)
        for point in points.children():
            x, y = point.arguments
            point.kind = 'Item'
            point.set_values()
            point.add('X', x)
            point.add('Y', y)


def _drawing(shape, index):
    if shape.kind != 'Shape' or shape.values:
        raise PcbError(f'{shape.path}: expected named board drawing fields')
    rename(shape, {'Type': 'Layer', 'Layer': 'LayId', 'ShapeType': 'Type',
        **{'Picture_'+name: 'Picture'+name for name in
           ('Raster', 'Transparent', 'Width', 'Height', 'Proportions', 'Flipped')}})
    booleans(shape, (name for name, field in graphic_records.SHAPE.fields.items() if field.kind == 'boolean'))
    if shape.child('TextAngle') is None:
        # Current ASC reads this compatibility value numerically when the
        # full angle is absent. It does not encode another geometry frame.
        shape.add('TextAngle', _key(shape, 'Orientation', default=0))
    elif (orientation := shape.child('Orientation')) is not None:
        orientation.detach()
    bitmap = _key(shape, 'BitmapIndex', default=-1)
    if shape.scalar('Type') == 7:
        shape.add('BitmapIndex', picture_reference_index(shape, bitmap))
    previous = _key(shape, 'OldNumber')
    text, name = shape.child('TextLines'), shape.child('Name')
    if shape.child('TextLine') is not None:
        raise PcbError(f'{shape.path}: duplicate drawing text')
    if text is not None:
        if text.values:
            raise PcbError(f'{text.path}: expected text-line records')
        for row in text.children():
            if row.kind != 'TextLine' or len(row.values) != 1 or row.children() or not isinstance(row.values[0], str):
                raise PcbError(f'{row.path}: expected one text line')
            row.kind = 'pt'
        text.kind = 'TextLine'
    elif name is not None:
        if len(name.values) != 1 or name.children() or not isinstance(name.values[0], str):
            raise PcbError(f'{name.path}: expected one compatibility text line')
        shape.add('TextLine').add('pt', name.arguments[0])
    if name is not None:
        name.detach()
    _vector(shape)
    _points(shape.one('Points'))
    shape.set_values(index)
    return DrawingInput(shape, previous)


def _pour(pour, index):
    if pour.kind != 'CopperPour' or pour.values:
        raise PcbError(f'{pour.path}: expected named copper-pour fields')
    rename(pour, {'Layer': 'Lay', 'NetNumber': 'NetId'})
    booleans(pour, (name for name, field in graphic_records.POUR.fields.items() if field.kind == 'boolean'))
    area = pour.one('MinimumArea')
    if len(area.arguments) != 1 or area.children():
        raise PcbError(f'{area.path}: expected one minimum-area threshold')
    value = area.arguments[0]
    area.set_values(Value(square_length(value), 'number', source=value.source))
    _points(pour.one('Points'))
    collections = [pour.child(name) for name in ('Lines', 'Polygons', 'SpokeLine')]
    if any(node is not None for node in collections):
        fill = pour.add('Fill')
        for collection in collections:
            if collection is None:
                continue
            if collection.values:
                raise PcbError(f'{collection.path}: expected fill geometry records')
            collection.move_to(fill)
            if collection.kind == 'Polygons':
                for polygon in collection.children():
                    if (polygon.kind != 'Poly' or len(polygon.values) != 1
                            or type(polygon.values[0]) is not int):
                        raise PcbError(f'{polygon.path}: expected one fill-region selector')
                    region = polygon.arguments[0]
                    rows = polygon.children()
                    points = polygon.add('Points')
                    for row in rows:
                        numeric_row(row, 2)
                        row.move_to(points)
                    polygon.set_values()
                    polygon.add('Region', region)
            else:
                width = collection.kind == 'SpokeLine'
                names = ('X1', 'Y1', 'X2', 'Y2') + (('Width',) if width else ()) + ('Region',)
                for line in collection.children():
                    values = numeric_row(line, len(names), integers=(len(names)-1,))
                    line.kind = 'Line'
                    line.set_values()
                    for name, value in zip(names, values):
                        line.add(name, value)
    counted = pour.child('Regions_Counted')
    regions = False
    if counted is not None:
        if len(counted.arguments) != 1 or counted.children():
            raise PcbError(f'{counted.path}: expected one region-counting flag')
        regions = boolean(counted.arguments[0], counted.path).value
        counted.detach()
    previous = _key(pour, 'OldNumber')
    if pour.child('RatlineMode') is None:
        # ASC does not supply this connection-display preference. Use the
        # model's ordinary initial choice, without changing an explicit value.
        pour.add('RatlineMode', graphic_records.POUR.fields['RatlineMode'].default)
    pour.set_values(index)
    return PourInput(pour, previous, regions)


def _dimensions(collection):
    if collection is None:
        return
    if collection.values:
        raise PcbError(f'{collection.path}: expected dimension records')
    schema = (graphic_records.DIMENSION if collection.parent.kind == 'Board'
              else graphic_records.PATTERN_DIMENSION)
    for index, dimension in enumerate(collection.children()):
        if dimension.kind != 'Dimension' or dimension.values:
            raise PcbError(f'{dimension.path}: expected named dimension fields')
        booleans(dimension, (name for name, field in schema.fields.items() if field.kind == 'boolean'))
        if 'Selected' in schema.fields and dimension.child('Selected') is None:
            dimension.add('Selected', schema.fields['Selected'].default)
        dimension.set_values(index)


def unpack_graphics(board):
    """Return temporary graphic keys; authored geometry remains in the input tree."""
    booleans(board, ('Enabled',))
    if (outline := board.child('Points')) is not None:
        _points(outline, 3, flags=(2,))
    if (groups := board.child('Groups')) is not None:
        if groups.values:
            raise PcbError(f'{groups.path}: expected group records')
        for group in groups.children():
            values = numeric_row(group, 6, kind='Group', flags=(3, 4, 5), integers=(0,))
            group.set_values(*values[:3])
            group.add('Enabled', values[3])
            group.add('Selected', values[4])
            # The last flag is temporary editor state, not group meaning.
    if (layers := board.child('NonSignals')) is not None:
        for layer in layers.children():
            if (layer.kind != 'NonSignal' or len(layer.values) != 4 or layer.children()
                    or not isinstance(layer.values[0], str)
                    or any(type(value) is not int for value in layer.values[1:])):
                raise PcbError(f'{layer.path}: expected name, color, number and side')
    _dimensions(board.child('Dimensions'))
    for component in board.select('Components/Component'):
        _dimensions(component.one('Pattern').child('Dimensions'))
    drawings = tuple(_drawing(shape, i) for i, shape in enumerate(board.select('Shapes/Shape')))
    pours = tuple(_pour(pour, i) for i, pour in enumerate(board.select('CopperPours/CopperPour')))
    return drawings, pours
