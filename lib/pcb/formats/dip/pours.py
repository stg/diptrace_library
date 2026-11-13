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
    reader.add_into(pour, 'MinimumArea', Value(area, 'number', source=threshold.source))


def _region(reader, node):
    if reader.header.version > 33:
        reader.field_into(node, 'Region', 'integer')
    else:
        reader.add_into(node, 'Region', -1)


def _segments(reader, fill, name, *, width=False):
    segments = reader.add(fill, name)
    for _ in range(reader.count('pour '+name)):
        segment = reader.add(segments, 'Line')
        _fields(reader, segment, 'number', 'X1 Y1 X2 Y2')
        if width:
            reader.field_into(segment, 'Width', 'number')
        _region(reader, segment)
    return segments


def read_base_pours(reader, board):
    """Read authored pour data and available calculated geometry independently.

    Binary files carry fill collections even for an unfilled pour. Other input
    formats may omit them altogether; that absence is represented by no Fill
    child when those adapters import a document.
    """
    pours = reader.add(board, 'CopperPours')
    upgrades = []
    for index in range(reader.count('copper pours')):
        start = reader.pos
        pour = reader.add(pours, 'CopperPour', index)
        _fields(reader, pour, 'boolean', 'Enabled Selected Poured')
        _fields(reader, pour, 'number', 'LineWidth Clearance')
        _area(reader, pour)
        _fields(reader, pour, 'integer', 'Group Lay NetId')
        points = reader.add(pour, 'Points')
        reader.points(points, reader.count('pour boundary points'))
        fill = reader.add(pour, 'Fill')
        _segments(reader, fill, 'Lines')
        polygons = reader.add(fill, 'Polygons')
        for _ in range(reader.count('pour fill polygons')):
            polygon = reader.add(polygons, 'Poly')
            points = reader.add(polygon, 'Points')
            reader.points(points, reader.count('pour polygon points'))
            _region(reader, polygon)
        _fields(reader, pour, 'integer', 'Type Spoke')
        _fields(reader, pour, 'number', 'LineSpacing SpokeWidth')
        _segments(reader, fill, 'SpokeLine', width=True)
        reader.field_into(pour, 'UseNetClearance', 'boolean')
        reader.boolean()  # Discarded compatibility setting.
        _fields(reader, pour, 'boolean', 'Locked SnapToBoard')
        reader.field_into(pour, 'BoardClearance', 'number')
        _fields(reader, pour, 'boolean', 'IslandRegion IslandInternal IslandConnection')
        previous_number = reader.integer()
        _fields(reader, pour, 'boolean', 'ViaDirect SMD_Separate')
        reader.field_into(pour, 'SMD_Spoke', 'integer')
        reader.field_into(pour, 'SMD_SpokeWidth', 'number')
        reader.field_into(pour, 'PanelExclude', 'boolean')
        if reader.header.version > 33:
            counted = reader.boolean()
            reader.field_into(pour, 'Priority', 'integer')
        else:
            counted = False
            reader.add_into(pour, 'Priority', 0)
        counted = counted and reader.header.version >= 38
        pour.source = SourceSpan('dip', start, reader.pos, reader.source)
        upgrades.append(PourUpgrade(pour, previous_number, counted))
    return tuple(upgrades)
