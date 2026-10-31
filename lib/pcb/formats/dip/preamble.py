"""Initial board, layer and routing-rule sections of the DIP stream.

These are boundary records. The completed importer resolves index relationships
and modernizes legacy choices before returning its document model.
"""
from dataclasses import dataclass
from decimal import Decimal

from ....common.model import Value


@dataclass(frozen=True)
class InitialState:
    component_count: int
    legacy_picture_count: int
    legacy_markings: tuple


def _fields(reader, parent, kind, names):
    reader.fields(parent, ((name, kind) for name in names.split()))


def _outline(reader, board):
    reader.field(board, 'Enabled', 'boolean')
    # The old bounding rectangle is recalculated on load. Authored outline
    # geometry is the following ordered point sequence.
    for _ in range(4):
        reader.number()
    points = board.add('Points')
    for _ in range(reader.count('board outline points')):
        reader.record(points, 'pt', 'number', 'number', 'boolean')
    reader.field(board, 'PanelExclude', 'boolean')
    _fields(reader, board, 'integer', 'PanelX PanelY')
    _fields(reader, board, 'number', 'PanelDX PanelDY')
    if reader.header.version > 31:
        reader.field(board, 'RailShow', 'boolean')
        _fields(reader, board, 'number', 'RailLeft RailRight RailTop RailBottom')
    else:
        board.add('RailShow', False)
        for name in ('RailLeft', 'RailRight', 'RailTop', 'RailBottom'):
            board.add(name, 0)


def _layers(reader, board):
    layers = board.add('Layers')
    for _ in range(reader.count('copper layers')):
        enabled, number, color, name = (reader.argument(kind)
            for kind in ('boolean', 'integer', 'color', 'text'))
        layer = layers.add('Layer', name)
        for key, value in (('Enabled', enabled), ('Number', number), ('Color', color)):
            layer.add(key, value)
        _fields(reader, layer, 'integer', 'Type HoleType NetNumber')
        reader.field(layer, 'HoleRing', 'number')
        reader.field(layer, 'Locked', 'boolean')


def _hierarchy(reader, board):
    non_signals = board.add('NonSignals')
    sheets = board.add('HierarchySheets')
    if reader.header.version <= 32:
        return
    for _ in range(reader.count('non-signal layers')):
        reader.record(non_signals, 'NonSignal', 'text', 'color', 'integer', 'integer')
    for _ in range(reader.count('hierarchy sheets')):
        sheet = reader.record(sheets, 'HSheet', 'text', 'integer')
        blocks = sheet.add('UpdateIds')
        for _ in range(reader.count('hierarchy blocks')):
            reader.record(blocks, 'UId', 'integer', 'text')


def _routing_rules(reader, board):
    vias = board.add('ViaStyles')
    for _ in range(reader.count('via styles')):
        reader.record(vias, 'ViaStyle', 'text', 'boolean', 'number', 'number', 'integer', 'integer')
    classes = board.add('NetClasses')
    for _ in range(reader.count('net classes')):
        net_class = reader.record(classes, 'NetClass', 'text')
        reader.field(net_class, 'Type', 'integer')
        _fields(reader, net_class, 'boolean', 'AllLayers CheckLength AllVias PerformDRC')
        layers = net_class.add('LayProperties')
        for _ in range(reader.count('class layer properties')):
            layer = layers.add('LayProperty')
            _fields(reader, layer, 'number', 'Width MinWidth MaxWidth Clearance DifClearance')
            details = layer.add('ClearDetails')
            for _ in range(4):
                reader.record(details, 'pt', *('number',)*5)
        _fields(reader, net_class, 'number', 'MinLength MaxLength')
        allowed_vias = net_class.add('AllowedVias')
        for _ in range(reader.count('allowed via styles')):
            reader.record(allowed_vias, 'ViaStyle', 'integer')
        _fields(reader, net_class, 'boolean', 'RoutePriority RouteMaxVias RouteMaxIncorrectWay RouteAllLayers')
        _fields(reader, net_class, 'integer', 'PriorityValue MaxViasValue')
        _fields(reader, net_class, 'number', 'MaxIncorrectWayValue MaxUncoupledLength Tolerance')
        routing_layers = net_class.add('RouteLayers')
        for _ in range(reader.count('routing layer flags')):
            reader.record(routing_layers, 'Item', 'boolean')
        reader.field(net_class, 'HiddenID', 'integer')
    reader.field(board, 'ClassToClass', 'boolean')
    clearances = board.add('ClassClearances')
    for _ in range(reader.count('class clearance rows')):
        row = clearances.add('Row')
        for _ in range(reader.count('class clearance columns')):
            cell = row.add('Cell')
            reader.field(cell, 'AllLayers', 'boolean')
            values = cell.add('Values')
            for _ in range(reader.count('class clearances')):
                reader.record(values, 'Item', 'number')


def read_initial_sections(reader, root):
    """Read through the component count; return transient upgrade inputs.

    This function is one stage of a full-file decoder, not a partial-document
    public import. Legacy label choices are consumed by later modernization.
    """
    scale = reader.field(root, 'Scale', 'number')
    factor = min(Decimal(1000), max(Decimal('.01'), scale.values[0]))
    sign, digits, exponent = factor.as_tuple()
    scale.set_argument(0, Value(Decimal((sign, digits, exponent+2)), 'number', '%',
                               source=scale.arguments[0].source))
    _fields(reader, root, 'integer', 'Xpos Ypos')
    board = root.add('Board')
    reader.field(board, 'RelSchem', 'text')
    _outline(reader, board)
    _fields(reader, board, 'boolean', 'Locked Toplock Bottomlock')
    _layers(reader, board)
    picture_count = reader.count('legacy picture companions')
    legacy_markings = tuple(reader.integer() for _ in range(4))
    reader.field(board, 'CompFontSize', 'integer')
    reader.field(board, 'CompFontName', 'text')
    _fields(reader, board, 'number', 'OriginX OriginY')
    reader.field(board, 'PatternFontVector', 'boolean')
    _fields(reader, board, 'number', 'PatternFontWidth PatternFontScale')
    _fields(reader, board, 'boolean', 'AssyObjSilk AssyObjBorders AssyObjMarking AssyObjBoard AssyObjPads')
    _fields(reader, board, 'text', 'UserField1 UserField2')
    reader.field(board, 'LockNetStructure', 'boolean')
    _hierarchy(reader, board)
    _routing_rules(reader, board)
    return InitialState(reader.count('components'), picture_count, legacy_markings)
