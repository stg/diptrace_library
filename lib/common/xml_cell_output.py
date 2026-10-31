"""Shared XML projection of sheet title grids and styled text cells."""
from .cell_text import cell_lines
from .model import Element
from .title_records import TEXT_ALIGN, TITLE_BLOCKS, has_title_data
from .xml import set_attribute
from .xml_font_output import project_size
from .xml_output import enum_text, field, numeric, stroke_width


def bounds(target, values, units):
    if len(values) != 4:
        raise ValueError('cell bounds require four coordinates')
    for index, value in enumerate(values):
        set_attribute(target, ('X1', 'Y1', 'X2', 'Y2')[index],
                      numeric(units.length(value) * (-1 if index % 2 else 1)))


def text_lines(source, target):
    values = cell_lines(source)
    if values:
        text = target.add('TextLines')
        for value in values:
            field(text, 'TextLine', value)


def font(source, target, *, prefix='', units=None, fractional_font=True, color=True):
    for public, own in (('FontVector', 'VectorFont'), ('FontWidth', 'FontWidth'),
                        ('FontScale', 'FontScale'), ('FontColor', 'FontColor'), ('LineSpacing', 'LineSpacing')):
        if public == 'FontColor' and not color:
            continue
        value = source[prefix+own]
        if public == 'FontWidth' and units is not None:
            value = stroke_width(value, units)
        set_attribute(target, public, value)
    project_size(source, target, size=prefix+'FontSize', mono=prefix+'FontMono', fractional=fractional_font)


def append_table_grid(table, target, *, units, project_cell):
    """Write the shared column-major grid; adapters project cell style/content."""
    columns, rows = table.select('ColWidths/pt'), table.select('RowHeights/pt')
    cells = table.select('Cells/Cell')
    if len(cells) != len(columns)*len(rows):
        raise ValueError(f'{table.path}: table cells do not form the declared rectangle')
    for name, values in (('ColWidths', columns), ('RowHeights', rows)):
        if values:
            sizes = target.add(name)
            for value in values:
                field(sizes, 'Item', numeric(units.length(value.arguments[0])))
    if columns:
        output = target.add('Cells')
        for column in range(len(columns)):
            group = output.add('Cell')
            for source in cells[column*len(rows):(column+1)*len(rows)]:
                item = group.add('Cell')
                bounds(item, source.arguments, units)
                project_cell(source, item)


def project_title_block(grid, *, name, units, fractional_font=True):
    result = Element(name)
    field(result, 'Name', grid.arguments[1])
    for key in ('Width', 'Height'):
        set_attribute(result, key, numeric(units.length(grid.one(key).arguments[0])))
    columns, rows = grid.select('ColWidths/pt'), grid.select('RowHeights/pt')
    for public, values in (('ColumnWidths', columns), ('RowHeights', rows)):
        if values:
            target = result.add(public)
            for value in values:
                field(target, 'Item', numeric(units.length(value.arguments[0])))
    cells = grid.select('Cells/Cell')
    if len(cells) != len(columns)*len(rows):
        raise ValueError(f'{grid.path}: title cells do not form the declared rectangle')
    if columns:
        target = result.add('Cells')
        for column in range(len(columns)):
            group = target.add('Item')
            for cell in cells[column*len(rows):(column+1)*len(rows)]:
                item = group.add('Item')
                set_attribute(item, 'FieldId', cell.arguments[2])
                edges = cell.one('Edges').values
                if len(edges) != 4:
                    raise ValueError(f'{cell.path}: title cell requires four border choices')
                for public, value in zip(('TopLine', 'BottomLine', 'LeftLine', 'RightLine'), edges):
                    set_attribute(item, public, value)
    contents = grid.select('Contents/Content')
    if contents:
        fields = result.add('Fields')
        for index, source in enumerate(contents):
            item = fields.add('Field')
            set_attribute(item, 'Id', index)
            text_lines(source, item)
            field(item, 'FontName', source.scalar('FontName'))
            font(source, item, units=units, fractional_font=fractional_font)
            set_attribute(item, 'TextShow', enum_text(source.scalar('FontType'), ('Text', 'Sheet', 'File')))
            set_attribute(item, 'TextAlign', enum_text(source.scalar('Align'), TEXT_ALIGN))
            bounds(item, source.one('Placement').arguments, units)
    return result


def append_title_blocks(page, sheet, *, units, fractional_font=True):
    for grid in page.select('TitleBlocks/TitleBlock'):
        index = grid.values[0]
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(TITLE_BLOCKS):
            raise ValueError(f'{grid.path}: title block requires a known placement')
        if has_title_data(grid):
            sheet.append(project_title_block(grid, name=TITLE_BLOCKS[index], units=units, fractional_font=fractional_font))
