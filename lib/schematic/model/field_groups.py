"""Reusable named field groups from the public schematic vocabulary."""
from ...common.schema import Field, Record


SHOW = Field('Show', 'integer', required=True, default=0,
             description='Display choice: 0 Common, 1 Show, 2 Hide.')
SHOW_PART = Field('ShowPart', 'integer', required=True, default=0,
                  description='Part-name suffix choice: 0 Common, 1 Show, 2 Hide.')
ALIGN = Field('Align', 'integer', required=True, default=0,
              description='0 Common, 1 Center, 2 Top, 3 Bottom, 4 Left, 5 Right, 6 Corner, 7 Auto, 8 Position.')
POSITION = (
    ALIGN,
    Field('Horz', 'integer', required=True, default=0,
          description='Horizontal text alignment: 0 Center, 1 Right, -1 or 2 Left.'),
    Field('Vert', 'integer', required=True, default=0,
          description='Vertical text alignment: 0 Center, 1 Bottom, -1 or 2 Top.'),
    Field('X', 'number', required=True, default=0, unit='shared length', description='Local horizontal offset.'),
    Field('Y', 'number', required=True, default=0, unit='shared length', description='Local vertical offset.'),
    Field('Angle', 'number', required=True, default=0, unit='radians', description='Local text angle.'),
)


def group(name, members, description=''):
    return Record(name, {member.name: member for member in members},
                  tuple(member.name for member in members), description)


MARKING = group('Marking', (SHOW, *POSITION), 'A component label display and local placement.')
NAMED_MARKING = group('NamedMarking', (SHOW, SHOW_PART, *POSITION),
                      'A component name/reference label, including its part suffix choice.')
GLOBAL_MARKING = group('GlobalMarking', (SHOW, ALIGN), 'Default label display and alignment.')
GLOBAL_NAMED_MARKING = group('GlobalNamedMarking', (SHOW, SHOW_PART, ALIGN),
                             'Default name/reference label display and alignment.')
USER_FIELD = group('UserField', (
    Field('Name', 'text', required=True, default='', description='User-visible field name.'),
    Field('Value', 'text', required=True, default='', description='Field text or link.'),
    Field('Type', 'integer', required=True, default=0, description='0 Text, 1 Link.'),
))
COMPONENT_USER_FIELD = group('ComponentUserField', (*USER_FIELD.fields.values(), *MARKING.fields.values()),
                             'Component user text/link and its label display and placement.')

BOUNDS = group('Bounds', tuple(Field(name, 'number', required=True, default=0, unit='shared length')
                               for name in ('X1', 'Y1', 'X2', 'Y2')),
               'Two opposite corners, retaining their authored order.')
BORDERS = group('Borders', tuple(Field(name, 'boolean', required=True, default=False)
                                for name in ('TopLine', 'BottomLine', 'LeftLine', 'RightLine')))
POINT = group('Point', tuple(Field(name, 'number', required=True, default=0, unit='shared length')
                             for name in ('X', 'Y')))
TEXT_LINE = group('TextLine', (Field('Text', 'text', required=True, default='',
                                   description='Literal text, or calculated content while bound to a component field.'),))
COLUMN_WIDTH = group('ColumnWidth', (Field('Width', 'number', required=True, default=0, unit='shared length'),))
ROW_HEIGHT = group('RowHeight', (Field('Height', 'number', required=True, default=0, unit='shared length'),))


def grid_position(cell):
    if cell.parent is None or cell.parent.parent is None:
        return 0, 0
    rows = cell.parent.parent.child('RowHeights')
    height = len(rows.children('pt')) if rows is not None else 0
    if height == 0:
        raise ValueError('cell has no containing grid rows')
    return divmod(cell._ordinal(), height)


def grid_rows(cell):
    rows = cell.parent.parent.child('RowHeights')
    return ((rows, 'pt'),) if rows is not None else ()


GRID_FIELDS = {
    'Column': Field('Column', 'integer', getter=lambda cell: grid_position(cell)[0],
                    collection_dependencies=grid_rows,
                    ordinal_dependencies=lambda cell: (cell,),
                    description='Zero-based column in its containing grid.'),
    'Row': Field('Row', 'integer', getter=lambda cell: grid_position(cell)[1],
                 collection_dependencies=grid_rows,
                 ordinal_dependencies=lambda cell: (cell,),
                 description='Zero-based row in its containing grid.'),
}
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
