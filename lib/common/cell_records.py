"""Authored cell text/style/bounds and derived grid coordinates."""
from .schema import Child, Field, Record


def _row(name, fields, description=''):
    return Record(name, {field.name: field for field in fields},
                  parameters=tuple(field.name for field in fields), description=description)


BOUNDS = _row('Bounds', tuple(Field(name, 'number', required=True, default=0, unit='shared length')
                             for name in ('X1', 'Y1', 'X2', 'Y2')),
              'Two opposite corners, retaining their authored order.')
COLUMN_WIDTH = _row('ColumnWidth', (Field('Width', 'number', required=True, default=0, unit='shared length'),))
ROW_HEIGHT = _row('RowHeight', (Field('Height', 'number', required=True, default=0, unit='shared length'),))


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
                    collection_dependencies=grid_rows, ordinal_dependencies=lambda cell: (cell,),
                    description='Zero-based column in its containing grid.'),
    'Row': Field('Row', 'integer', getter=lambda cell: grid_position(cell)[1],
                 collection_dependencies=grid_rows, ordinal_dependencies=lambda cell: (cell,),
                 description='Zero-based row in its containing grid.'),
}
CELL = Record('Cell', {
    **{name: Field(name, kind, required=True) for name, kind in (
        ('FOrientation', 'boolean'), ('FontSize', 'number'), ('FontType', 'integer'),
        ('Align', 'integer'), ('FontColor', 'integer'), ('Text', 'text'), ('FontName', 'text'),
        ('VectorFont', 'boolean'), ('FontWidth', 'number'), ('FontScale', 'number'), ('LineSpacing', 'number'))},
    'FontMono': Field('FontMono', 'boolean', default=False),
    **BOUNDS.fields, **GRID_FIELDS,
}, BOUNDS.parameters, 'A table cell with authored bounds and derived grid position.')


def _collection(name, kind, record):
    return Record(name, {}, description='An ordered collection of '+record.name+' records.',
                  children={kind: Child(kind, record.name, maximum=None)})


CELLS = _collection('TableCells', 'Cell', CELL)
COLUMN_WIDTHS = _collection('ColumnWidths', 'pt', COLUMN_WIDTH)
ROW_HEIGHTS = _collection('RowHeights', 'pt', ROW_HEIGHT)
