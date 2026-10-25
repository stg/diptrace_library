"""Reusable named field groups from the public schematic vocabulary."""
from ...common.schema import Field, Record
from ...common.drawing_records import POINT, TEXT_LINE
from ...common.user_fields import USER_FIELD, COMPONENT_USER_FIELD
from ...common.label_records import SHOW, SHOW_PART, ALIGN, POSITION, MARKING
from ...common.cell_records import BOUNDS, COLUMN_WIDTH, ROW_HEIGHT, GRID_FIELDS


def group(name, members, description=''):
    return Record(name, {member.name: member for member in members},
                  tuple(member.name for member in members), description)


NAMED_MARKING = group('NamedMarking', (SHOW, SHOW_PART, *POSITION),
                      'A component name/reference label, including its part suffix choice.')
GLOBAL_MARKING = group('GlobalMarking', (SHOW, ALIGN), 'Default label display and alignment.')
GLOBAL_NAMED_MARKING = group('GlobalNamedMarking', (SHOW, SHOW_PART, ALIGN),
                             'Default name/reference label display and alignment.')

BORDERS = group('Borders', tuple(Field(name, 'boolean', required=True, default=False)
                                for name in ('TopLine', 'BottomLine', 'LeftLine', 'RightLine')))
TITLE_CELL = Record('TitleCell', {**GRID_FIELDS,
    'FieldId': Field('FieldId', 'integer', required=True, default=-1,
                     description='Field identity projection; -1 means no content.'),
    'Edges': Field('Edges', 'tuple', required=True, members=tuple(BORDERS.fields.values())),
}, ('Column', 'Row', 'FieldId'))
TITLE_BLOCK = Record('TitleBlock', {
    'Position': Field('Position', 'integer', getter=lambda node: node._ordinal(),
                      ordinal_dependencies=lambda node: (node,),
                      description='0 BottomRight, 1 BottomLeft, 2 TopRight, 3 TopLeft, 4 ExtTopLeft, 5 ExtBottomLeft.'),
    'Name': Field('Name', 'text', required=True, default=''),
    'Width': Field('Width', 'number', required=True, default=0, unit='shared length'),
    'Height': Field('Height', 'number', required=True, default=0, unit='shared length'),
}, ('Position', 'Name'))

NET_CLASS = group('NetClass', (
    Field('Name', 'text', required=True, default=''),
    Field('Type', 'integer', required=True, default=0, description='0 Normal, 1 Differential Pair.'),
    Field('Width', 'number', required=True, default=-1, unit='shared length', description='-1 inherits the common width.'),
    Field('Clearance', 'number', required=True, default=-1, unit='shared length', description='-1 inherits common clearance.'),
    Field('UpdateId', 'integer', required=True, default=0, description='Persistent class update identity.'),
    *(Field(name, 'number', required=True, default=default, unit='shared length') for name, default in
      (('DifClearance', -1), ('MaxUncoupledLength', 0), ('Tolerance', 0), ('Phase', 0), ('Phase_ErrorLength', 0))),
))


def _marking_definition(name):
    named = name.removesuffix('_Global') in ('ShowName', 'ShowRefDes')
    if name.endswith('_Global'):
        return GLOBAL_NAMED_MARKING if named else GLOBAL_MARKING
    return NAMED_MARKING if named else MARKING


MARKING_GROUPS = {name+suffix: _marking_definition(name+suffix)
                  for name in ('ShowName', 'ShowRefDes', 'ShowValue', 'ShowManufacturer', 'ShowDatasheet')
                  for suffix in ('', '_Global')}
TUPLE_GROUPS = {**MARKING_GROUPS, 'Edges': BORDERS, 'Placement': BOUNDS}


def marking_definition(name):
    return MARKING_GROUPS[name]


def tuple_definition(name):
    return TUPLE_GROUPS[name]
