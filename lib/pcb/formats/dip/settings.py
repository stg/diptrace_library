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
    settings = board.add('Settings')
    reader.field(settings, 'GridSize', 'number')
    reader.field(settings, 'GridEnabled', 'boolean')
    reader.field(settings, 'YGridSize', 'number')
    _fields(reader, settings, 'boolean', 'YGridIdentical OriginEnabled')
    reader.field(settings, 'AxisColor', 'color')
    sheet = board.child('SheetSettings')
    if sheet is None:
        sheet = board.add('SheetSettings')
    _fields(reader, sheet, 'boolean', 'DisplayTitles DisplaySheet')
    _fields(reader, settings, 'boolean', 'FlipTextAuto AssyPads AssySilk AssyPatBorders')
    reader.boolean()  # Discarded assembly-display compatibility setting.
    reader.field(settings, 'AssyBoardOutline', 'boolean')
    _fields(reader, settings, 'integer', 'JumperLayer LayerDisplayMode')
    reader.field(settings, 'EditInactiveLayer', 'boolean')
    _fields(reader, settings, 'number', 'SilkLineWidth TableLineWidth TitlesLineWidth BoardOutlineWidth')
    units = tuple(reader.boolean() for _ in range(3))
    return DisplayUpgrade(settings, units)


def read_rule_settings(reader, board):
    """Read initial routing defaults, design rules and connectivity choices."""
    routing = board.one('Settings').add('Routing')
    reader.field(routing, 'Router', 'integer')
    _fields(reader, routing, 'number',
            'TraceWidth TraceClearance PadClearance BoardClearance ViaSize')
    reader.field(routing, 'ViaApply', 'integer')
    _fields(reader, routing, 'number', 'FanoutLength ViaHole')
    drc = read_drc(reader, board)
    reader.field(drc, 'ShowList', 'boolean')
    connectivity = board.add('ConnectivityCheck')
    _fields(reader, connectivity, 'boolean', 'Traces Shapes CopperPours')
    return drc


def read_drc(reader, owner, kind='DRC'):
    """Read the rule set shared by current and last-used check settings."""
    drc = owner.add(kind)
    reader.field(drc, 'Name', 'text')
    _fields(reader, drc, 'boolean',
            'CheckClearance CheckSize CheckJumpers CheckCopperPours '
            'CheckClassToClass CheckSilk CheckLength AllLayers')
    clearances = drc.add('LayClearances')
    kinds = ('Trace', 'Via', 'Pad', 'Smd', 'Copper', 'Drill', 'Board')
    for layer in range(reader.count('DRC clearance layers')):
        row = clearances.add('LayClearance', layer)
        details = row.add('ClearanceDetails')
        for first in range(6):
            for second in range(7):
                value = reader.argument('number')
                if second >= first:
                    details.add(kinds[first]+'To'+kinds[second], value)
    sizes = drc.add('LaySizes')
    for layer in range(reader.count('DRC size layers')):
        size = sizes.add('LaySize', layer)
        _fields(reader, size, 'number',
                'MinTrace MinDrill MinRing MaxRing MaxPlatedHole MaxNonPlatedHole')
    return drc


def read_camera_extension(reader, root):
    """Use full-precision viewport coordinates when supplied by the file."""
    if reader.header.version > 41:
        for name in ('Xpos', 'Ypos'):
            reader.field(root, name, 'number', replace=True)


def read_grid_extension(reader, board):
    """Read the fine grid step and per-component placement clearance."""
    if reader.header.version <= 45:
        return
    grid = reader.field(board.one('Settings'), 'GridSize', 'number', replace=True)
    grid.set_values(grid_step_value(grid.values[0], reader.integer()))
    for component in board.select('Components/Component'):
        reader.field(component, 'PlacementClearance', 'number')
