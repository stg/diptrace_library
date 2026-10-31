"""Authored XML copper-pour geometry; unavailable calculated fill stays absent."""
from decimal import Decimal

from ....common.xml_records import enum_value, length, area
from ....common.xml_library_values import read_points
from ..assembly.graphic_inputs import PourInput
from ..errors import PcbError
from .keys import position, unique_id


TYPES = ('Solid', 'Horizontal Lines', 'Vertical Lines', 'Cross 45', 'Cross 90')
SPOKES = ('Direct', '2 spoke 90', '2 spoke', '4 spoke 45', '4 spoke')
RATLINES = ('Automaticaly', 'All Ratlines', 'Do Not Hide')
LENGTH_DEFAULTS = dict(Clearance=Decimal('.99'), LineWidth=Decimal('1.905'),
    LineSpacing=Decimal('1.905'), SpokeWidth=Decimal('.99'), SMD_SpokeWidth=Decimal('.99'),
    BoardClearance=Decimal('1.9812'))


def read_pours(record, board, *, units, layers, version):
    collection, seen, prepared = board.add('CopperPours'), {}, []
    for index, source in enumerate(record.rows('CopperPours', 'CopperPour')):
        key = unique_id(source, seen, label='copper pour')
        pour = collection.add('CopperPour', index)
        seen[key] = pour
        for name, default in (('Enabled', True), ('Selected', False), ('Poured', False), ('UseNetClearance', False),
                              ('Locked', False), ('SnapToBoard', False), ('IslandRegion', False),
                              ('IslandInternal', False), ('IslandConnection', False), ('ViaDirect', True),
                              ('SMD_Separate', False), ('PanelExclude', False)):
            pour.add(name, source.boolean(name, default))
        for name, labels in (('Type', TYPES), ('Spoke', SPOKES), ('SMD_Spoke', SPOKES), ('RatlineMode', RATLINES)):
            pour.add(name, enum_value(source.value(name, labels[0]), labels))
        for name, default in LENGTH_DEFAULTS.items():
            pour.add(name, length(source.number(name), units) if source.has(name) else default)
        if source.has('MinimumArea'):
            if not version.physical_pour_area:
                raise PcbError(f'{source.node.path}: earlier XML pour-area units are not mapped')
            pour.add('MinimumArea', area(source.number('MinimumArea'), units))
        else:
            pour.add('MinimumArea', 9)
        for name, default in (('Group', -1), ('NetId', -1), ('Priority', 0), ('ShieldGroup', -1),
                              ('TraceShieldGroup', -1)):
            pour.add(name, source.integer(name, default))
        pour.add('Lay', position(source.integer('Lay'), layers,
                                 label='pour copper layer', path=source.node.path) if source.has('Lay') else 0)
        points = pour.add('Points')
        for vertex in read_points(source, units=units):
            points.append(vertex)
        counted = source.boolean('RegionsDone', False)
        source.finish()
        prepared.append(PourInput(pour, key, counted))
    return tuple(prepared)
