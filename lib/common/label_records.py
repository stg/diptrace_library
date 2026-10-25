"""Shared label display choices and local placement, without layout algorithms."""
from .schema import Field, Record


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
MARKING = Record('Marking', {field.name: field for field in (SHOW, *POSITION)},
                 parameters=tuple(field.name for field in (SHOW, *POSITION)),
                 description='A component label display and local placement.')
