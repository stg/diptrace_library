"""Shared binary title-block cells, borders and content records."""
from .model import SourceSpan


def read_text_content(reader, cell):
    """Read the text style and placement shared by title and table cells."""
    reader.field(cell, 'FOrientation', 'boolean')
    for name in ('FontSize', 'FontType', 'Align'):
        reader.field(cell, name, 'integer')
    reader.field(cell, 'FontColor', 'color')
    reader.field(cell, 'Text', 'text')
    reader.field(cell, 'FontName', 'text')
    cell.add('Placement', *(reader.argument('number') for _ in range(4)))
    reader.field(cell, 'VectorFont', 'boolean')
    for name in ('FontWidth', 'FontScale'):
        reader.field(cell, name, 'number')
    return cell


def read_title_block(r, parent, index):
    """Read editable cells, borders, content and text styles."""
    start = r.pos
    grid = parent.add("TitleBlock", index, r.argument('text'))
    r.field(grid, "Width", "number")
    r.field(grid, "Height", "number")
    columns, rows = r.count("title columns"), r.count("title rows")
    widths = grid.add("ColWidths")
    for _ in range(columns):
        widths.add("pt", r.argument('number'))
    heights = grid.add("RowHeights")
    for _ in range(rows):
        heights.add("pt", r.argument('number'))
    if columns * rows > (len(r.data) - r.pos) // 7:
        raise r.error_type(f"title grid dimensions exceed remaining data at byte {r.pos:#x}")
    cells = grid.add("Cells")
    for column in range(columns):
        for row in range(rows):
            cell = cells.add("Cell", column, row, r.argument('integer'))
            cell.add("Edges", *(r.argument('boolean') for _ in range(4)))
    contents = grid.add("Contents")
    for index in range(r.count("title cell contents")):
        read_text_content(r, contents.add("Content", index))
    grid.source = SourceSpan(r.source_format, start, r.pos, r.source)
    return grid
