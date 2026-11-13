"""PCB display and editing settings from the initial settings section."""
from dataclasses import dataclass

from ....common.model import Element
from ....common.binary_records import grid_step_value
from .preamble import _fields


@dataclass(frozen=True)
class DisplayUpgrade:
    settings: Element
    unit_choices: tuple


def read_display_settings(reader, board):
    settings = reader.add(board, 'Settings')
    reader.field_into(settings, 'GridSize', 'number')
    reader.field_into(settings, 'GridEnabled', 'boolean')
    reader.field_into(settings, 'YGridSize', 'number')
    _fields(reader, settings, 'boolean', 'YGridIdentical OriginEnabled')
    reader.field_into(settings, 'AxisColor', 'color')
    sheet = board.child('SheetSettings')
    if sheet is None:
        sheet = reader.add(board, 'SheetSettings')
    _fields(reader, sheet, 'boolean', 'DisplayTitles DisplaySheet')
    _fields(reader, settings, 'boolean', 'FlipTextAuto AssyPads AssySilk AssyPatBorders')
    reader.boolean()  # Discarded assembly-display compatibility setting.
    reader.field_into(settings, 'AssyBoardOutline', 'boolean')
    _fields(reader, settings, 'integer', 'JumperLayer LayerDisplayMode')
    reader.field_into(settings, 'EditInactiveLayer', 'boolean')
    _fields(reader, settings, 'number', 'SilkLineWidth TableLineWidth TitlesLineWidth BoardOutlineWidth')
    units = tuple(reader.boolean() for _ in range(3))
    return DisplayUpgrade(settings, units)


def read_rule_settings(reader, board):
    """Read initial routing defaults, design rules and connectivity choices."""
    routing = reader.add(board.one('Settings'), 'Routing')
    reader.field_into(routing, 'Router', 'integer')
    _fields(reader, routing, 'number',
            'TraceWidth TraceClearance PadClearance BoardClearance ViaSize')
    reader.field_into(routing, 'ViaApply', 'integer')
    _fields(reader, routing, 'number', 'FanoutLength ViaHole')
    drc = read_drc(reader, board)
    reader.field_into(drc, 'ShowList', 'boolean')
    connectivity = reader.add(board, 'ConnectivityCheck')
    _fields(reader, connectivity, 'boolean', 'Traces Shapes CopperPours')
    return drc


def read_drc(reader, owner, kind='DRC'):
    """Read the rule set shared by current and last-used check settings."""
    drc = reader.add(owner, kind)
    reader.field_into(drc, 'Name', 'text')
    _fields(reader, drc, 'boolean',
            'CheckClearance CheckSize CheckJumpers CheckCopperPours '
            'CheckClassToClass CheckSilk CheckLength AllLayers')
    clearances = reader.add(drc, 'LayClearances')
    kinds = ('Trace', 'Via', 'Pad', 'Smd', 'Copper', 'Drill', 'Board')
    for layer in range(reader.count('DRC clearance layers')):
        row = reader.add(clearances, 'LayClearance', layer)
        details = reader.add(row, 'ClearanceDetails')
        for first in range(6):
            for second in range(7):
                value = reader.argument('number')
                if second >= first:
                    reader.add_into(details, kinds[first]+'To'+kinds[second], value)
    sizes = reader.add(drc, 'LaySizes')
    for layer in range(reader.count('DRC size layers')):
        size = reader.add(sizes, 'LaySize', layer)
        _fields(reader, size, 'number',
                'MinTrace MinDrill MinRing MaxRing MaxPlatedHole MaxNonPlatedHole')
    return drc


def read_camera_extension(reader, root):
    """Use full-precision viewport coordinates when supplied by the file."""
    if reader.header.version > 41:
        for name in ('Xpos', 'Ypos'):
            reader.field_into(root, name, 'number', replace=True)


def read_grid_extension(reader, board):
    """Read the fine grid step and per-component placement clearance."""
    if reader.header.version <= 45:
        return
    grid = reader.field(board.one('Settings'), 'GridSize', 'number', replace=True)
    grid.set_values(grid_step_value(grid.values[0], reader.integer()))
    for component in board.select('Components/Component'):
        reader.field_into(component, 'PlacementClearance', 'number')
