"""Generate the binary document prefix from current board/rule data.

This is a section writer, through the component count. It cannot produce a
complete DIP file by itself. Later sections supply full geometry and settings.
"""
from decimal import Decimal

from ....common.picture_sources import picture_reference_index
from ...model import definitions, board_rules, rule_records, graphic_records, hierarchy_records
from ..errors import PcbError
from ..output_indices import OutputIndices, ordered_layer_rows
from ..output_validation import check, check_tree, field_value


def _rows(owner, path, layers, *, uniform=False):
    return ordered_layer_rows(owner.select(path), layers, uniform=uniform, path=owner.path+'/'+path)


def _check_collections(board):
    """Preflight the owned prefix trees before generating any binary bytes."""
    for name, schema in (
        ('Points', graphic_records.OUTLINE_POINTS),
        ('Layers', board_rules.COLLECTIONS['Layers']),
        ('ViaStyles', board_rules.COLLECTIONS['ViaStyles']),
        ('NetClasses', board_rules.COLLECTIONS['NetClasses']),
        ('ClassClearances', rule_records.COLLECTIONS['ClassClearances']),
        ('NonSignals', graphic_records.COLLECTIONS['NonSignals']),
        ('HierarchySheets', hierarchy_records.SHEETS),
    ):
        if (collection := board.child(name)) is not None:
            check_tree(collection, schema, destination='DIP')


def _outline(writer, board):
    writer.scalar(board, 'Enabled', 'boolean')
    points = board.select('Points/pt')
    xs, ys = [point['X'] for point in points], [point['Y'] for point in points]
    # This compatibility box is recalculated by the loader. It is generated,
    # never retained as a second authoritative description of the outline.
    for value in (min(xs, default=0), min(ys, default=0), max(xs, default=0), max(ys, default=0)):
        writer.number(value)
    writer.integer(len(points))
    for point in points:
        writer.scalars(point, 'number', 'X Y')
        writer.scalar(point, 'Arc', 'boolean')
    writer.scalar(board, 'PanelExclude', 'boolean', default=False)
    writer.scalars(board, 'integer', 'PanelX PanelY', defaults={'PanelX': 1, 'PanelY': 1})
    writer.scalars(board, 'number', 'PanelDX PanelDY', defaults={'PanelDX': 0, 'PanelDY': 0})
    writer.scalar(board, 'RailShow', 'boolean', default=False)
    writer.scalars(board, 'number', 'RailLeft RailRight RailTop RailBottom',
                   defaults=dict.fromkeys(('RailLeft', 'RailRight', 'RailTop', 'RailBottom'), 0))


def _layers(writer, board):
    layers = tuple(board.select('Layers/Layer'))
    writer.integer(len(layers))
    for layer in layers:
        writer.scalar(layer, 'Enabled', 'boolean')
        writer.integer(layer['Number'])
        writer.scalar(layer, 'Color', 'color')
        writer.scalar(layer, 'Name', 'text')
        writer.scalars(layer, 'integer', 'Type HoleType NetNumber')
        writer.scalar(layer, 'HoleRing', 'number')
        writer.scalar(layer, 'Locked', 'boolean')
    return layers


def _hierarchy(writer, board):
    layers = board.select('NonSignals/NonSignal')
    writer.integer(len(layers))
    for layer in layers:
        writer.scalar(layer, 'Name', 'text')
        writer.scalar(layer, 'Color', 'color')
        writer.scalars(layer, 'integer', 'Id Side')
    sheets = board.select('HierarchySheets/HSheet')
    writer.integer(len(sheets))
    for sheet in sheets:
        writer.scalar(sheet, 'Name', 'text')
        writer.scalar(sheet, 'Number', 'integer')
        blocks = sheet.select('UpdateIds/UId')
        writer.integer(len(blocks))
        for block in blocks:
            writer.scalar(block, 'Id', 'integer')
            writer.scalar(block, 'Name', 'text')


def _classes(writer, board, layers, indices):
    vias = board.select('ViaStyles/ViaStyle')
    writer.integer(len(vias))
    for via in vias:
        writer.scalar(via, 'Name', 'text')
        writer.scalar(via, 'Through', 'boolean')
        writer.scalars(via, 'number', 'Size HoleSize')
        writer.scalars(via, 'integer', 'Lay1 Lay2')
    writer.integer(len(indices.classes))
    for current in indices.classes:
        writer.scalar(current, 'Name', 'text')
        writer.scalar(current, 'Type', 'integer')
        writer.scalars(current, 'boolean', 'AllLayers CheckLength AllVias PerformDRC')
        properties = _rows(current, 'LayProperties/LayProperty', layers, uniform=field_value(current, 'AllLayers'))
        writer.integer(len(properties))
        for row in properties:
            writer.scalars(row, 'number', 'Width MinWidth MaxWidth Clearance DifClearance')
            details = row.child('ClearanceDetails')
            for first in range(4):
                for second in range(5):
                    name = rule_records.CLEARANCE_KINDS[first]+'To'+rule_records.CLEARANCE_KINDS[second]
                    writer.number(-1 if second < first or details is None else field_value(details, name))
        # Public lengths can be integers, floats or decimals independently.
        # Use decimal arithmetic for the generated compatibility interval.
        fixed, delta = (Decimal(str(field_value(current, name)))
                        for name in ('FixedLength', 'LengthDelta'))
        writer.number(fixed-delta/2 if fixed >= 0 else 0)
        writer.number(fixed+delta/2 if fixed >= 0 else 0)
        allowed = current.select('AllowedVias/ViaStyle')
        writer.integer(len(allowed))
        for member in allowed:
            if member['Via'] is None:
                raise PcbError(f'{member.path}: allowed via requires a current via style')
            writer.integer(member['Id'])
        writer.scalars(current, 'boolean', 'RoutePriority RouteMaxVias RouteMaxIncorrectWay RouteAllLayers')
        writer.scalars(current, 'integer', 'PriorityValue MaxViasValue')
        writer.scalars(current, 'number', 'MaxIncorrectWayValue MaxUncoupledLength Tolerance')
        route_layers = _rows(current, 'RouteLayers/Item', layers)
        writer.integer(len(route_layers))
        for row in route_layers:
            writer.scalar(row, 'Enabled', 'boolean')
        writer.scalar(current, 'HiddenID', 'integer')


def _clearances(writer, board, layers, indices):
    by_pair = {}
    for cell in board.select('ClassClearances/Cell'):
        if cell['Class1'] is None or cell['Class2'] is None:
            raise PcbError(f'{cell.path}: class clearance needs two current classes')
        pair = tuple(sorted((indices.class_number(cell['Class1']), indices.class_number(cell['Class2']))))
        if pair in by_pair:
            raise PcbError(f'{cell.path}: duplicate symmetric class clearance')
        if field_value(cell, 'AllLayers'):
            if cell.child('LayerClearances') is not None:
                raise PcbError(f'{cell.path}: uniform clearance has inactive layer-specific data')
            values = (cell.get('Clearance'),)
        else:
            if cell.get('Clearance') is not None:
                raise PcbError(f'{cell.path}: layer-specific clearance has an inactive uniform value')
            values = tuple(row['Clearance'] for row in _rows(cell, 'LayerClearances/LayerClearance', layers))
        by_pair[pair] = field_value(cell, 'AllLayers'), values
    writer.scalar(board, 'ClassToClass', 'boolean')
    count = max((pair[1]+1 for pair in by_pair), default=0)
    writer.integer(count)
    for first in range(count):
        writer.integer(count)
        for second in range(count):
            uniform, values = by_pair.get(tuple(sorted((first, second))), (True, (None,)))
            writer.boolean(uniform)
            writer.integer(len(values))
            for value in values:
                writer.number(-1 if value is None else value)


def write_initial_sections(writer, document, *, indices=None):
    """Write header and initial data only; never claim a complete DIP result."""
    check(document.root, definitions.DOCUMENT, destination='DIP')
    board = document.one('/Board')
    check(board, definitions.BOARD, destination='DIP')
    _check_collections(board)
    indices = indices or OutputIndices(board)
    writer.header()
    factor = Decimal(str(document.root.get('Scale', 100)))
    if factor.is_finite():
        sign, digits, exponent = factor.as_tuple()
        factor = Decimal((sign, digits, exponent-2))
    writer.number(factor)
    for name in ('Xpos', 'Ypos'):
        writer.integer(round(document.root.get(name, 0)))
    writer.scalar(board, 'RelSchem', 'text', default='')
    _outline(writer, board)
    writer.scalars(board, 'boolean', 'Locked Toplock Bottomlock', defaults=dict.fromkeys(('Locked','Toplock','Bottomlock'), False))
    layers = _layers(writer, board)
    pictures = [picture_reference_index(shape, shape.get('BitmapIndex', -1)) for shape in board.select('Shapes/Shape')]
    writer.integer(max(pictures, default=-1)+1)
    # Modern marking properties supersede these two unused legacy selections.
    for value in (0, 6, 0, 6):
        writer.integer(value)
    writer.scalar(board, 'CompFontSize', 'integer', default=2)
    writer.scalar(board, 'CompFontName', 'text', default='')
    writer.scalars(board, 'number', 'OriginX OriginY', defaults={'OriginX': 0, 'OriginY': 0})
    writer.scalar(board, 'PatternFontVector', 'boolean', default=True)
    writer.scalars(board, 'number', 'PatternFontWidth PatternFontScale', defaults={'PatternFontWidth': -1, 'PatternFontScale': 1})
    writer.scalars(board, 'boolean', 'AssyObjSilk AssyObjBorders AssyObjMarking AssyObjBoard AssyObjPads',
                   defaults=dict.fromkeys(('AssyObjSilk','AssyObjBorders','AssyObjMarking','AssyObjBoard','AssyObjPads'), False))
    writer.scalars(board, 'text', 'UserField1 UserField2', defaults={'UserField1': '', 'UserField2': ''})
    writer.scalar(board, 'LockNetStructure', 'boolean', default=False)
    _hierarchy(writer, board)
    _classes(writer, board, layers, indices)
    _clearances(writer, board, layers, indices)
    writer.integer(len(board.select('Components/Component')))
