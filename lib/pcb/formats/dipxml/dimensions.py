"""Board dimensions and temporary XML attachment keys for shared assembly."""
from ....common.xml_records import enum_value, length, point
from ....common.xml_footprint_vocabulary import LAYERS, POINTER_MODES
from ....common.xml_font_import import read_font
from .font import read_width


TYPES = ('Horizontal', 'Vertical', 'Free', 'Radius', 'Pointer')
CONNECTIONS = ('Pad', 'Pattern Shape', 'Pattern Hole', 'Net', 'Plane', 'Shape',
               'Board Outline', 'Origin', 'Panel', 'None')


def _selectors(mode, owner, member, placements):
    if mode in (0, 1, 2):
        placed = placements.get(owner)
        if placed is None:
            return owner, -1
        members = {0: placed.pad_positions, 1: placed.shape_positions, 2: placed.hole_positions}
        return owner, members[mode].get(member, -1)
    return owner, member


def read_dimensions(record, board, *, units, placements, version):
    collection = board.add('Dimensions')
    for index, source in enumerate(record.rows('Dimensions', 'Dimension')):
        source.integer('Id', index)  # Output counter, not an attachment identity.
        dimension = collection.add('Dimension', index)
        for name, default in (('Enabled', True), ('Selected', False), ('Locked', False), ('PanelExclude', False)):
            dimension.add(name, source.boolean(name, default))
        dimension.add('Type', enum_value(source.value('Type', 'Free'), TYPES))
        dimension.add('Layer', enum_value(source.value('Layer', 'Top Dimension'), LAYERS))
        dimension.add('Group', source.integer('Group', -1))
        dimension.add('NonSignal', source.integer('NonSignal', 0))
        for side in ('1', '2'):
            mode = enum_value(source.value('Connected'+side, -1), CONNECTIONS, negative='None')
            owner, member = _selectors(mode, source.integer('Object'+side, 0), source.integer('SubObject'+side, 0),
                                       placements)
            for name, value in (('Connected', mode), ('Object', owner), ('SubObject', member),
                                ('Point', source.integer('Point'+side, 0))):
                dimension.add(name+side, value)
        for suffix in ('1', '2', 'D'):
            for axis, value in zip(('X', 'Y'), point(source, units, ('X'+suffix, 'Y'+suffix), 0)):
                dimension.add(axis+suffix, value)
        arrow = source.number('ArrowSize') if source.has('ArrowSize') else None
        dimension.add('ArrowSize', length(arrow, units) if arrow is not None and version.physical_dimension_arrow
                      else arrow if arrow is not None else 3)
        dimension.add('Units', enum_value(source.value('Units', 'Common'), ('Common', 'inch', 'mil', 'mm')))
        dimension.add('VectorFont', source.boolean('FontVector', True))
        dimension.add('FontName', source.text('FontName', 'Tahoma'))
        read_font(source, dimension, default=4)
        dimension.add('FontWidth', read_width(source, units=units, version=version))
        dimension.add('FontScale', source.number('FontScale', 1))
        dimension.add('ShowUnits', source.boolean('ShowUnits', False))
        dimension.add('Angle', source.number('Angle', 0))
        dimension.add('ExternalRadius', source.integer('ExternalRadius', -1))
        dimension.add('PointerMode', enum_value(source.value('PointerMode', 'Coordinates'), POINTER_MODES))
        dimension.add('PointerText', source.text('PointerText', ''))
        source.finish()
