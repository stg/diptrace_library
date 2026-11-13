"""Shared binary title-block cells, borders and content records."""
from .model import SourceSpan
from .cell_text import cell_text


def read_text_content(reader, cell):
    """Read the text style and placement shared by title and table cells."""
    reader.field_into(cell, 'FOrientation', 'boolean')
    for name in ('FontSize', 'FontType', 'Align'):
        reader.field_into(cell, name, 'integer')
    reader.field_into(cell, 'FontColor', 'color')
    reader.field_into(cell, 'Text', 'text')
    reader.field_into(cell, 'FontName', 'text')
    reader.add_into(cell, 'Placement', *(reader.argument('number') for _ in range(4)))
    reader.field_into(cell, 'VectorFont', 'boolean')
    for name in ('FontWidth', 'FontScale'):
        reader.field_into(cell, name, 'number')
    return cell


def read_title_block(r, parent, index):
    """Read editable cells, borders, content and text styles."""
    start = r.pos
    grid = r.add(parent, "TitleBlock", index, r.argument('text'))
    r.field_into(grid, "Width", "number")
    r.field_into(grid, "Height", "number")
    columns, rows = r.count("title columns"), r.count("title rows")
    widths = r.add(grid, "ColWidths")
    for _ in range(columns):
        r.add_into(widths, "pt", r.argument('number'))
    heights = r.add(grid, "RowHeights")
    for _ in range(rows):
        r.add_into(heights, "pt", r.argument('number'))
    if columns * rows > (len(r.data) - r.pos) // 7:
        raise r.error_type(f"title grid dimensions exceed remaining data at byte {r.pos:#x}")
    cells = r.add(grid, "Cells")
    for column in range(columns):
        for row in range(rows):
            cell = r.add(cells, "Cell", column, row, r.argument('integer'))
            r.add_into(cell, "Edges", *(r.argument('boolean') for _ in range(4)))
    contents = r.add(grid, "Contents")
    for index in range(r.count("title cell contents")):
        read_text_content(r, r.add(contents, "Content", index))
    grid.source = SourceSpan(r.source_format, start, r.pos, r.source)
    return grid


def write_text_content(writer, cell):
    """Write the shared styled text and its authored placement rectangle."""
    writer.field(cell, 'FOrientation', 'boolean')
    writer.fields(cell, 'integer', 'FontSize FontType Align')
    writer.field(cell, 'FontColor', 'color')
    writer.text(cell_text(cell))
    writer.field(cell, 'FontName', 'text')
    placement = cell.child('Placement')
    writer.values(placement if placement is not None else cell, 'number '*4)
    writer.field(cell, 'VectorFont', 'boolean')
    writer.fields(cell, 'number', 'FontWidth FontScale')


def write_title_block(writer, grid):
    """Write one grid in column-major order using current content selectors."""
    writer.text(grid.values[1])
    writer.fields(grid, 'number', 'Width Height')
    columns, rows = grid.select('ColWidths/pt'), grid.select('RowHeights/pt')
    writer.integer(len(columns))
    writer.integer(len(rows))
    for size in columns+rows:
        writer.values(size, 'number')
    cells = grid.select('Cells/Cell')
    if len(cells) != len(columns)*len(rows):
        raise ValueError(f'{grid.path}: title cells do not form a rectangle')
    for cell in cells:
        writer.field(cell, 'FieldId', 'integer')
        writer.values(cell.one('Edges'), 'boolean '*4)
    contents = grid.select('Contents/Content')
    writer.integer(len(contents))
    for content in contents:
        write_text_content(writer, content)
