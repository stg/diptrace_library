"""Binary display, routing and DRC records with identity-scoped rule rows."""
from ....common.binary_records import write_grid_step
from ....common.units import DISPLAY_UNITS
from ...model import settings_records, rule_records
from ..errors import PcbError
from ..output_indices import ordered_layer_rows
from ..output_validation import check_tree, field_value


def write_display_settings(writer, document):
    board = document.one('/Board')
    settings, sheet = board.child('Settings'), board.child('SheetSettings')
    if settings is None or sheet is None:
        raise PcbError(f'{board.path}: display and sheet settings are needed for binary output')
    check_tree(settings, settings_records.SETTINGS, destination='DIP')
    writer.field(settings, 'GridSize', 'number')
    writer.field(settings, 'GridEnabled', 'boolean')
    writer.field(settings, 'YGridSize', 'number')
    writer.fields(settings, 'boolean', 'YGridIdentical OriginEnabled')
    writer.field(settings, 'AxisColor', 'color')
    writer.fields(sheet, 'boolean', 'DisplayTitles DisplaySheet')
    writer.fields(settings, 'boolean', 'FlipTextAuto AssyPads AssySilk AssyPatBorders')
    writer.boolean(False)
    writer.field(settings, 'AssyBoardOutline', 'boolean')
    writer.fields(settings, 'integer', 'JumperLayer LayerDisplayMode')
    writer.field(settings, 'EditInactiveLayer', 'boolean')
    writer.fields(settings, 'number', 'SilkLineWidth TableLineWidth TitlesLineWidth BoardOutlineWidth')
    for unit in DISPLAY_UNITS:
        writer.boolean(document.root['Units'] == unit)


def drc_rows(drc, name, board):
    return ordered_layer_rows(drc.select(name+'/'+('LayClearance' if name == 'LayClearances' else 'LaySize')),
        board.select('Layers/Layer'), uniform=field_value(drc, 'AllLayers'), path=drc.path+'/'+name)


def write_drc(writer, board, kind='DRC'):
    drc = board.child(kind)
    if drc is None:
        raise PcbError(f'{board.path}: {kind} settings are needed for binary output')
    check_tree(drc, rule_records.DRC, destination='DIP')
    writer.field(drc, 'Name', 'text')
    writer.fields(drc, 'boolean', 'CheckClearance CheckSize CheckJumpers CheckCopperPours '
                  'CheckClassToClass CheckSilk CheckLength AllLayers')
    rows = drc_rows(drc, 'LayClearances', board)
    writer.integer(len(rows))
    for row in rows:
        details = row.child('ClearanceDetails')
        for first in range(6):
            for second in range(7):
                name = rule_records.CLEARANCE_KINDS[first]+'To'+rule_records.CLEARANCE_KINDS[second]
                writer.number(-1 if second < first or details is None else field_value(details, name))
    rows = drc_rows(drc, 'LaySizes', board)
    writer.integer(len(rows))
    for row in rows:
        writer.fields(row, 'number', 'MinTrace MinDrill MinRing MaxRing MaxPlatedHole MaxNonPlatedHole')


def write_rule_settings(writer, board):
    routing = board.one('Settings/Routing')
    writer.field(routing, 'Router', 'integer')
    for name in ('TraceWidth', 'TraceClearance'):
        current = routing[name]
        writer.number(0 if current is None else current)
    writer.fields(routing, 'number', 'PadClearance BoardClearance ViaSize')
    writer.field(routing, 'ViaApply', 'integer')
    writer.fields(routing, 'number', 'FanoutLength ViaHole')
    write_drc(writer, board)
    writer.field(board.one('DRC'), 'ShowList', 'boolean')
    connectivity = board.one('ConnectivityCheck')
    check_tree(connectivity, settings_records.CONNECTIVITY, destination='DIP')
    writer.fields(connectivity, 'boolean', 'Traces Shapes CopperPours')


def write_mask_settings(writer, board):
    writer.fields(board.one('Settings'), 'number', 'SolderMaskSwell PasteMaskShrink')
    for kind in ('DRC', 'LastDRC'):
        drc = board.one(kind)
        writer.fields(drc, 'boolean', 'CheckKeepouts CheckSameNet CheckSameComponentPads')
        for row in drc_rows(drc, 'LayClearances', board):
            writer.fields(row, 'number', 'SameTraceToTrace SameSmdToVia SameSmdToPad SameSmdToSmd')


def write_grid_extension(writer, board):
    write_grid_step(writer, board.one('Settings')['GridSize'])
    for component in board.select('Components/Component'):
        writer.field(component, 'PlacementClearance', 'number')


def write_display_extensions(writer, board):
    panel = board.one('Settings/LayerPanel')
    writer.fields(panel, 'boolean', 'TopAssy TopMask TopPaste BotAssy BotMask BotPaste Board '
                  'TopTerminals BotTerminals TopCourtyard BotCourtyard TopOutline BotOutline '
                  'TopDimensions BotDimensions')
    layers = board.select('NonSignals/NonSignal')
    supplied = [index for index, layer in enumerate(layers) if layer.get('Visible') is not None]
    count = supplied[-1]+1 if supplied else 0
    if supplied != list(range(count)):
        raise PcbError('Binary custom-layer visibility requires choices for all preceding layers')
    writer.integer(count)
    for layer in layers[:count]:
        writer.field(layer, 'Visible', 'boolean')
    for kind in ('DRC', 'LastDRC'):
        writer.field(board.one(kind), 'CheckCourtyard', 'boolean')
        writer.field(board.one(kind), 'SilkClearance', 'number')
    writer.field(board.one('Settings'), 'ShowCompFiducials', 'boolean')
