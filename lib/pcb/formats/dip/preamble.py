"""Initial board, layer and routing-rule sections of the DIP stream.

These are boundary records. The completed importer resolves index relationships
and modernizes legacy choices before returning its document model.
"""
from dataclasses import dataclass
from decimal import Decimal

from ....common.model import Value
from ....common.numbers import decimal_scale


@dataclass(frozen=True)
class InitialState:
    component_count: int
    legacy_picture_count: int
    legacy_markings: tuple


def _fields(reader, parent, kind, names):
    reader.fields(parent, ((name, kind) for name in names.split()))


def _outline(reader, board):
    reader.field_into(board, 'Enabled', 'boolean')
    # The old bounding rectangle is recalculated on load. Authored outline
    # geometry is the following ordered point sequence.
    for _ in range(4):
        reader.number()
    points = reader.add(board, 'Points')
    for _ in range(reader.count('board outline points')):
        reader.record(points, 'pt', 'number', 'number', 'boolean')
    reader.field_into(board, 'PanelExclude', 'boolean')
    _fields(reader, board, 'integer', 'PanelX PanelY')
    _fields(reader, board, 'number', 'PanelDX PanelDY')
    if reader.header.version > 31:
        reader.field_into(board, 'RailShow', 'boolean')
        _fields(reader, board, 'number', 'RailLeft RailRight RailTop RailBottom')
    else:
        reader.add_into(board, 'RailShow', False)
        for name in ('RailLeft', 'RailRight', 'RailTop', 'RailBottom'):
            reader.add_into(board, name, 0)


def _layers(reader, board):
    layers = reader.add(board, 'Layers')
    for _ in range(reader.count('copper layers')):
        enabled, number, color, name = (reader.argument(kind)
            for kind in ('boolean', 'integer', 'color', 'text'))
        layer = reader.add(layers, 'Layer', name)
        for key, value in (('Enabled', enabled), ('Number', number), ('Color', color)):
            reader.add_into(layer, key, value)
        _fields(reader, layer, 'integer', 'Type HoleType NetNumber')
        reader.field_into(layer, 'HoleRing', 'number')
        reader.field_into(layer, 'Locked', 'boolean')


def _hierarchy(reader, board):
    non_signals = reader.add(board, 'NonSignals')
    sheets = reader.add(board, 'HierarchySheets')
    if reader.header.version <= 32:
        return
    for _ in range(reader.count('non-signal layers')):
        reader.record(non_signals, 'NonSignal', 'text', 'color', 'integer', 'integer')
    for _ in range(reader.count('hierarchy sheets')):
        sheet = reader.record(sheets, 'HSheet', 'text', 'integer')
        blocks = reader.add(sheet, 'UpdateIds')
        for _ in range(reader.count('hierarchy blocks')):
            reader.record(blocks, 'UId', 'integer', 'text')


def _routing_rules(reader, board):
    vias = reader.add(board, 'ViaStyles')
    for _ in range(reader.count('via styles')):
        reader.record(vias, 'ViaStyle', 'text', 'boolean', 'number', 'number', 'integer', 'integer')
    classes = reader.add(board, 'NetClasses')
    for _ in range(reader.count('net classes')):
        net_class = reader.record(classes, 'NetClass', 'text')
        reader.field_into(net_class, 'Type', 'integer')
        _fields(reader, net_class, 'boolean', 'AllLayers CheckLength AllVias PerformDRC')
        layers = reader.add(net_class, 'LayProperties')
        for _ in range(reader.count('class layer properties')):
            layer = reader.add(layers, 'LayProperty')
            _fields(reader, layer, 'number', 'Width MinWidth MaxWidth Clearance DifClearance')
            details = reader.add(layer, 'ClearDetails')
            for _ in range(4):
                reader.record(details, 'pt', *('number',)*5)
        _fields(reader, net_class, 'number', 'MinLength MaxLength')
        allowed_vias = reader.add(net_class, 'AllowedVias')
        for _ in range(reader.count('allowed via styles')):
            reader.record(allowed_vias, 'ViaStyle', 'integer')
        _fields(reader, net_class, 'boolean', 'RoutePriority RouteMaxVias RouteMaxIncorrectWay RouteAllLayers')
        _fields(reader, net_class, 'integer', 'PriorityValue MaxViasValue')
        _fields(reader, net_class, 'number', 'MaxIncorrectWayValue MaxUncoupledLength Tolerance')
        routing_layers = reader.add(net_class, 'RouteLayers')
        for _ in range(reader.count('routing layer flags')):
            reader.record(routing_layers, 'Item', 'boolean')
        reader.field_into(net_class, 'HiddenID', 'integer')
    reader.field_into(board, 'ClassToClass', 'boolean')
    clearances = reader.add(board, 'ClassClearances')
    for _ in range(reader.count('class clearance rows')):
        row = reader.add(clearances, 'Row')
        for _ in range(reader.count('class clearance columns')):
            cell = reader.add(row, 'Cell')
            reader.field_into(cell, 'AllLayers', 'boolean')
            values = reader.add(cell, 'Values')
            for _ in range(reader.count('class clearances')):
                reader.record(values, 'Item', 'number')


def read_initial_sections(reader, root):
    """Read through the component count; return transient upgrade inputs.

    This function is one stage of a full-file decoder, not a partial-document
    public import. Legacy label choices are consumed by later modernization.
    """
    scale = reader.field(root, 'Scale', 'number')
    factor = min(Decimal(1000), max(Decimal('.01'), scale.values[0]))
    scale.set_argument(0, Value(decimal_scale(factor, 2), 'number', '%',
                               source=scale.arguments[0].source))
    _fields(reader, root, 'integer', 'Xpos Ypos')
    board = reader.add(root, 'Board')
    reader.field_into(board, 'RelSchem', 'text')
    _outline(reader, board)
    _fields(reader, board, 'boolean', 'Locked Toplock Bottomlock')
    _layers(reader, board)
    picture_count = reader.count('legacy picture companions')
    legacy_markings = tuple(reader.integer() for _ in range(4))
    reader.field_into(board, 'CompFontSize', 'integer')
    reader.field_into(board, 'CompFontName', 'text')
    _fields(reader, board, 'number', 'OriginX OriginY')
    reader.field_into(board, 'PatternFontVector', 'boolean')
    _fields(reader, board, 'number', 'PatternFontWidth PatternFontScale')
    _fields(reader, board, 'boolean', 'AssyObjSilk AssyObjBorders AssyObjMarking AssyObjBoard AssyObjPads')
    _fields(reader, board, 'text', 'UserField1 UserField2')
    reader.field_into(board, 'LockNetStructure', 'boolean')
    _hierarchy(reader, board)
    _routing_rules(reader, board)
    return InitialState(reader.count('components'), picture_count, legacy_markings)
