"""Public XML table grids and page title blocks from owned data."""
from .cell_text import cell_lines
from .dchxml import set_attribute
from .dchxml_settings import enum_text, field, numeric, stroke_width
from .model import Element
from .page_titles import has_title_data


TEXT_ALIGN = ('Left', 'Center', 'Right')
TITLE_BLOCKS = ('BottomRightBlock', 'BottomLeftBlock', 'TopRightBlock', 'TopLeftBlock',
                'ExtTopLeftBlock', 'ExtBottomLeftBlock')


def _bounds(target, values, units):
    if len(values) != 4:
        raise ValueError('cell bounds require four coordinates')
    for index, value in enumerate(values):
        set_attribute(target, ('X1', 'Y1', 'X2', 'Y2')[index],
                      numeric(units.length(value) * (-1 if index % 2 else 1)))


def _text(source, target):
    values = cell_lines(source)
    if values:
        text = target.add('TextLines')
        for value in values:
            field(text, 'TextLine', value)


def _font(source, target, *, prefix='', units=None, version=46):
    for public, own in (('FontVector', 'VectorFont'), ('FontSize', 'FontSize'), ('FontWidth', 'FontWidth'),
                        ('FontScale', 'FontScale'), ('FontColor', 'FontColor'), ('LineSpacing', 'LineSpacing')):
        value = source.one(prefix+own).arguments[0]
        if public == 'FontWidth' and units is not None:
            value = stroke_width(value, units)
        set_attribute(target, public, value)
    from .dchxml_fonts import project_size
    project_size(source, target, size=prefix+'FontSize', mono=prefix+'FontMono', version=version)


def project_table(table, *, index, units, version=46):
    result = Element('Table')
    set_attribute(result, 'Id', index)
    if table.scalar('HideBorder'):
        set_attribute(result, 'HideBorder', True)
    set_attribute(result, 'Sheet', table.scalar('Page'))
    _bounds(result, [table.one(name).arguments[0] for name in ('X1', 'Y1', 'X2', 'Y2')], units)
    set_attribute(result, 'Orientation', int(enum_text(table.scalar('Orientation'), ('0', '90', '180', '270'))))
    for public, own in (('CellWidth', 'DefCellWidth'), ('CellHeight', 'DefCellHeight')):
        set_attribute(result, public, numeric(units.length(table.one(own).arguments[0])))
    set_attribute(result, 'TextAlign', enum_text(table.scalar('DefAlign'), TEXT_ALIGN))
    _font(table, result, prefix='Def', version=version)
    if table.scalar('Group') >= 0:
        set_attribute(result, 'Group', table.scalar('Group'))
    field(result, 'FontName', table.scalar('DefFontName'))
    field(result, 'Name', table.scalar('Name'))
    columns, rows = table.select('ColWidths/pt'), table.select('RowHeights/pt')
    for name, values in (('ColWidths', columns), ('RowHeights', rows)):
        if values:
            target = result.add(name)
            for value in values:
                field(target, 'Item', numeric(units.length(value.arguments[0])))
    cells = table.select('Cells/Cell')
    if len(cells) != len(columns)*len(rows):
        raise ValueError(f'{table.path}: table cells do not form the declared rectangle')
    if columns:
        target = result.add('Cells')
        for column in range(len(columns)):
            group = target.add('Cell')
            for source in cells[column*len(rows):(column+1)*len(rows)]:
                item = group.add('Cell')
                _bounds(item, source.arguments, units)
                set_attribute(item, 'TextAlign', enum_text(source.scalar('Align'), TEXT_ALIGN))
                field(item, 'FontName', source.scalar('FontName'))
                _text(source, item)
                _font(source, item, version=version)
    for name in ('Selected', 'Locked'):
        if table.scalar(name):
            set_attribute(result, name, True)
    return result


def project_tables(schematic, *, units, version=46):
    result = Element('Tables')
    for index, table in enumerate(schematic.select('Tables/Table')):
        if table.scalar('Enabled'):
            result.append(project_table(table, index=index, units=units, version=version))
    return result


def project_title_block(grid, *, name, units, version=46):
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
            _text(source, item)
            field(item, 'FontName', source.scalar('FontName'))
            _font(source, item, units=units, version=version)
            set_attribute(item, 'TextShow', enum_text(source.scalar('FontType'), ('Text', 'Sheet', 'File')))
            set_attribute(item, 'TextAlign', enum_text(source.scalar('Align'), TEXT_ALIGN))
            _bounds(item, source.one('Placement').arguments, units)
    return result


def append_title_blocks(page, sheet, *, units, version=46):
    for grid in page.select('TitleBlocks/TitleBlock'):
        index = grid.values[0]
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(TITLE_BLOCKS):
            raise ValueError(f'{grid.path}: title block requires a known placement')
        if has_title_data(grid):
            sheet.append(project_title_block(grid, name=TITLE_BLOCKS[index], units=units, version=version))
