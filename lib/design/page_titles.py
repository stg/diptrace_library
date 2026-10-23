"""Title-grid content, separate from whether a title name is selected."""


def has_title_data(grid):
    """Distinguish an empty default slot from a stored name, layout or fields."""
    return bool(grid.values[1] or grid.scalar('Width', 0) or grid.scalar('Height', 0)
                or any(grid.one(name).children() for name in
                       ('ColWidths', 'RowHeights', 'Cells', 'Contents')))
