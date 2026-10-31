"""Copper-pour boundaries, settings and separately owned calculated fill."""
from dataclasses import dataclass
from ....common.model import Element, SourceSpan, Value
from ....common.units import square_length
from .preamble import _fields


@dataclass(frozen=True)
class PourUpgrade:
    pour: Element
    previous_number: int
    regions_counted: bool


def _area(reader, pour):
    threshold = reader.argument('number')
    area = square_length(threshold)
    pour.add('MinimumArea', Value(area, 'number', source=threshold.source))


def _region(reader, node):
    if reader.header.version > 33:
        reader.field(node, 'Region', 'integer')
    else:
        node.add('Region', -1)


def _segments(reader, fill, name, *, width=False):
    segments = fill.add(name)
    for _ in range(reader.count('pour '+name)):
        segment = segments.add('Line')
        _fields(reader, segment, 'number', 'X1 Y1 X2 Y2')
        if width:
            reader.field(segment, 'Width', 'number')
        _region(reader, segment)
    return segments


def read_base_pours(reader, board):
    """Read authored pour data and available calculated geometry independently.

    Binary files carry fill collections even for an unfilled pour. Other input
    formats may omit them altogether; that absence is represented by no Fill
    child when those adapters import a document.
    """
    pours = board.add('CopperPours')
    upgrades = []
    for index in range(reader.count('copper pours')):
        start = reader.pos
        pour = pours.add('CopperPour', index)
        _fields(reader, pour, 'boolean', 'Enabled Selected Poured')
        _fields(reader, pour, 'number', 'LineWidth Clearance')
        _area(reader, pour)
        _fields(reader, pour, 'integer', 'Group Lay NetId')
        points = pour.add('Points')
        for _ in range(reader.count('pour boundary points')):
            reader.record(points, 'pt', 'number', 'number')
        fill = pour.add('Fill')
        _segments(reader, fill, 'Lines')
        polygons = fill.add('Polygons')
        for _ in range(reader.count('pour fill polygons')):
            polygon = polygons.add('Poly')
            points = polygon.add('Points')
            for _ in range(reader.count('pour polygon points')):
                reader.record(points, 'pt', 'number', 'number')
            _region(reader, polygon)
        _fields(reader, pour, 'integer', 'Type Spoke')
        _fields(reader, pour, 'number', 'LineSpacing SpokeWidth')
        _segments(reader, fill, 'SpokeLine', width=True)
        reader.field(pour, 'UseNetClearance', 'boolean')
        reader.boolean()  # Discarded compatibility setting.
        _fields(reader, pour, 'boolean', 'Locked SnapToBoard')
        reader.field(pour, 'BoardClearance', 'number')
        _fields(reader, pour, 'boolean', 'IslandRegion IslandInternal IslandConnection')
        previous_number = reader.integer()
        _fields(reader, pour, 'boolean', 'ViaDirect SMD_Separate')
        reader.field(pour, 'SMD_Spoke', 'integer')
        reader.field(pour, 'SMD_SpokeWidth', 'number')
        reader.field(pour, 'PanelExclude', 'boolean')
        if reader.header.version > 33:
            counted = reader.boolean()
            reader.field(pour, 'Priority', 'integer')
        else:
            counted = False
            pour.add('Priority', 0)
        counted = counted and reader.header.version >= 38
        pour.source = SourceSpan('dip', start, reader.pos, reader.source)
        upgrades.append(PourUpgrade(pour, previous_number, counted))
    return tuple(upgrades)
