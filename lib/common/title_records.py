"""Sheet title grids and styled content shared by document families."""
from .schema import Child, Field, Record
from .cell_records import CELL, BOUNDS, GRID_FIELDS
from .model import Element


TEXT_ALIGN = ('Left', 'Center', 'Right')
TITLE_BLOCKS = ('BottomRightBlock', 'BottomLeftBlock', 'TopRightBlock', 'TopLeftBlock',
                'ExtTopLeftBlock', 'ExtBottomLeftBlock')
BORDERS = Record('Borders', {name: Field(name, 'boolean', required=True, default=False)
                            for name in ('TopLine', 'BottomLine', 'LeftLine', 'RightLine')},
                 ('TopLine', 'BottomLine', 'LeftLine', 'RightLine'))
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
_STYLE_NAMES = ('FOrientation', 'FontSize', 'FontType', 'Align', 'FontColor', 'Text', 'FontName',
                'VectorFont', 'FontWidth', 'FontScale', 'LineSpacing')
TITLE_FIELD = Record('TitleField', {
    **{name: CELL.fields[name] for name in _STYLE_NAMES},
    'Placement': Field('Placement', 'tuple', required=True, members=tuple(BOUNDS.fields.values())),
    'FontMono': CELL.fields['FontMono'],
    'Index': Field('Index', 'integer', required=True, default=0, getter=lambda node: node._ordinal(),
                   ordinal_dependencies=lambda node: (node,)),
}, ('Index',))


def new_title_blocks():
    """Create the six named sheet anchors without invented grid content."""
    titles = Element('TitleBlocks')
    for index in range(len(TITLE_BLOCKS)):
        grid = titles.add('TitleBlock', index, '')
        grid.add('Width', 0)
        grid.add('Height', 0)
        for name in ('ColWidths', 'RowHeights', 'Cells', 'Contents'):
            grid.add(name)
    return titles


def has_title_data(grid):
    """Distinguish an empty default slot from a name, layout or styled fields."""
    return bool(grid.values[1] or grid.scalar('Width', 0) or grid.scalar('Height', 0)
                or any(grid.one(name).children() for name in
                       ('ColWidths', 'RowHeights', 'Cells', 'Contents')))
