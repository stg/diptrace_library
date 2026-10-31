"""Expand public ASC board-rule records before identity-based assembly."""
from decimal import Decimal

from ....common.asc_text import raw_token
from ....common.model import Value
from ...model.board_rules import NET_CLASS
from .values import boolean, booleans, counted_rows, numeric_row, rename
from ..errors import PcbError


def _rows(owner, kind):
    if owner.values or any(row.kind != kind for row in owner.children()):
        raise PcbError(f'{owner.path}: expected {kind} records')
    return owner.children()


def _layers(collection):
    for layer in _rows(collection, 'Name'):
        if len(layer.arguments) > 1:
            raise PcbError(f'{layer.path}: expected at most one copper-layer name token')
        name = layer.arguments[0] if layer.arguments else Value('', 'string')
        # This text position keeps quote marks and numeric spelling literally.
        # Exclamation marks, including those inside quotes, stand for spaces.
        layer.set_values(Value(raw_token(name).replace('!', ' '), 'string', source=name.source))
        layer.kind = 'Layer'
        booleans(layer, ('Enabled', 'Locked'))
        radius = None
        for field in tuple(layer.children()):
            if field.kind not in ('HoleSize', 'HoleRing'):
                continue
            if (len(field.arguments) != 1 or field.children()
                    or field.arguments[0].kind != 'number' or field.arguments[0].unit):
                raise PcbError(f'{field.path}: expected one hole dimension')
            value = field.arguments[0]
            # Both public spellings update the same dimension. Input order
            # determines its final value when declarations disagree.
            radius = Value(Decimal(value.value)/2, 'number', source=value.source) if field.kind == 'HoleSize' else value
            field.detach()
        if radius is not None:
            layer.add('HoleRing', radius)


def _vias(collection):
    for style in _rows(collection, 'ViaStyle'):
        values = list(style.arguments)
        if len(values) != 6 or not isinstance(values[0].value, str) or style.children():
            raise PcbError(f'{style.path}: expected name, through, size, hole and layer span')
        values[1] = boolean(values[1], style.path)
        for position in range(2, 6):
            value = values[position]
            if (value.kind != 'number' or value.unit
                    or position >= 4 and type(value.value) is not int):
                raise PcbError(f'{style.path}: invalid via value at column {position+1}')
        style.set_values(*values)


def _classes(collection):
    flags = tuple(name for name, field in NET_CLASS.fields.items() if field.kind == 'boolean')
    for net_class in _rows(collection, 'NetClass'):
        if len(net_class.values) != 1 or not isinstance(net_class.values[0], str):
            raise PcbError(f'{net_class.path}: expected one net-class name')
        rename(net_class, {'RouteParity': 'RoutePriority', 'ParityValue': 'PriorityValue',
                           'ViaStyle': 'AllowedVias'})
        booleans(net_class, flags)
        properties = net_class.child('LayProperties')
        if properties is not None:
            for row in _rows(properties, 'LayProperty'):
                if row.values:
                    raise PcbError(f'{row.path}: expected named layer properties')
                # ASC's two labels are reversed relative to the conceptual
                # minimum/maximum names used by the current model and XML.
                # This is a vocabulary mapping, independent of their values.
                for name in ('MinWidth', 'MaxWidth'):
                    if len(row.children(name)) > 1:
                        raise PcbError(f'{row.path}: ambiguous {name} fields')
                for field in row.children():
                    if field.kind in ('MinWidth', 'MaxWidth'):
                        field.kind = 'MaxWidth' if field.kind == 'MinWidth' else 'MinWidth'
                details = row.child('ClearDetails')
                if details is not None:
                    rows = _rows(details, 'pt')
                    if len(rows) != 4:
                        raise PcbError(f'{details.path}: expected four clearance rows')
                    for item in rows:
                        numeric_row(item, 5)
        allowed = net_class.child('AllowedVias')
        if allowed is not None:
            for row in _rows(allowed, 'pt'):
                numeric_row(row, 1, integers=(0,))
                row.kind = 'ViaStyle'
        route_layers = net_class.child('RouteLayers')
        if route_layers is not None:
            for row in _rows(route_layers, 'pt'):
                row.set_values(*numeric_row(row, 1, flags=(0,)))
                row.kind = 'Item'


def _class_clearances(board):
    rename(board, {'CTC_Cells': 'ClassClearances'})
    matrix = board.child('ClassClearances')
    if matrix is None:
        return
    # The header counts classes on each axis, rather than the emitted cells.
    if (len(matrix.values) != 1 or type(matrix.values[0]) is not int
            or matrix.values[0] < 0):
        raise PcbError(f'{matrix.path}: expected a class-matrix dimension')
    dimension = matrix.values[0]
    seen = set()
    for cell in matrix.children():
        values = cell.arguments
        if (cell.kind != 'Cell' or len(values) != 3
                or any(type(value.value) is not int or not 0 <= value.value < dimension
                       for value in values[:2])):
            raise PcbError(f'{cell.path}: invalid class-clearance coordinates')
        pair = cell.values[:2]
        if pair in seen:
            raise PcbError(f'{cell.path}: duplicate class-clearance coordinates')
        seen.add(pair)
        uniform = boolean(values[2], cell.path)
        rows = cell.children()
        for row in rows:
            numeric_row(row, 1)
        cell.set_values(*values[:2])
        cell.add('AllLayers', uniform)
        numbers = cell.add('Values')
        for row in rows:
            row.kind = 'Item'
            row.move_to(numbers)
    if len(seen) != dimension * dimension:
        raise PcbError(f'{matrix.path}: dimension does not match cells')
    matrix.set_values()


def _stack(board):
    source = board.child('LayerStack')
    if source is None:
        return
    if (len(source.values) != 2 or not isinstance(source.values[0], str)
            or board.child('LayerStackName') is not None or board.child('LayerStackItems') is not None):
        raise PcbError(f'{source.path}: expected one stack name and item count')
    name = source.arguments[0]
    source.set_values(source.arguments[1])
    rows = counted_rows(source)
    board.add('LayerStackName', name)
    source.kind = 'LayerStackItems'
    for index, row in enumerate(rows):
        values = list(row.arguments)
        if (row.kind != 'pt' or len(values) != 7 or row.children()
                or not isinstance(values[1].value, str)):
            raise PcbError(f'{row.path}: expected layer, material and five properties')
        values[3] = boolean(values[3], row.path)
        for position in (0, 2, 4, 5, 6):
            value = values[position]
            if (value.kind != 'number' or value.unit
                    or position in (0, 2) and type(value.value) is not int):
                raise PcbError(f'{row.path}: invalid stack value at column {position+1}')
        row.kind = 'LayerStackItem'
        row.set_values(index)
        row.add('Lay', values[0])
        material = row.add('Material')
        for field, value in zip(('Name', 'Type', 'VariableThickness', 'Thickness', 'Constant', 'TraceWidth'), values[1:]):
            material.add(field, value)


def unpack_rules(board):
    """Prepare layers, via styles, classes and stackup without binding indices."""
    for name, unpack in (('Layers', _layers), ('ViaStyles', _vias), ('NetClasses', _classes)):
        if (collection := board.child(name)) is not None:
            unpack(collection)
    booleans(board, ('ClassToClass',))
    _class_clearances(board)
    _stack(board)
