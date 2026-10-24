"""Normalize public table grids and title fields into editable own records."""
from .dchxml_import_values import enum_value, length, point, replace_rows
from .dchxml_tables import TEXT_ALIGN, TITLE_BLOCKS
from .model import Element
from .schematic_new import fields


def read_font(record, target, *, prefix='', units=None):
    target.set_field(prefix+'VectorFont', record.boolean('FontVector', True))
    from .dchxml_fonts import read_font as read_size_and_mono, read_text_extent
    read_size_and_mono(record, target, size=prefix+'FontSize', prefix=prefix)
    read_text_extent(record)
    width = record.number('FontWidth', -1)
    target.set_field(prefix+'FontWidth', length(width, units) if units is not None and width.value >= 0 else width)
    target.set_field(prefix+'FontScale', record.number('FontScale', 1))
    target.set_field(prefix+'FontColor', record.integer('FontColor', 0))
    target.set_field(prefix+'LineSpacing', record.number('LineSpacing', 1.2))


def read_lines(record, target, *, container='TextLines', kind='TextLine'):
    lines = []
    for line in record.rows(container, kind):
        value = line.content()
        if value.kind != 'string':
            raise ValueError(f'{line.node.path}: text line requires text')
        lines.append(value.value)
        line.finish(allow_text=True)
    target.set_field('Text', '\n'.join(lines))


def _sizes(record, name, units):
    result = []
    for item in record.rows(name, 'Item'):
        result.append(Element('pt', length(item.content(), units)))
        item.finish(allow_text=True)
    return result


def read_title_blocks(sheet, page, *, units):
    for index, name in enumerate(TITLE_BLOCKS):
        source = sheet.take(name)
        if source is None:
            continue
        grid = page.one('TitleBlocks').children('TitleBlock')[index]
        grid.set_argument(1, source.text('Name', ''))
        for key in ('Width', 'Height'):
            grid.set_field(key, length(source.number(key, 0), units))
        columns, rows = _sizes(source, 'ColumnWidths', units), _sizes(source, 'RowHeights', units)
        replace_rows(grid, 'ColWidths', columns)
        replace_rows(grid, 'RowHeights', rows)
        contents, ids = [], {}
        for position, item in enumerate(source.rows('Fields', 'Field')):
            key = item.integer('Id', position)
            if key in ids:
                raise ValueError(f'{item.node.path}: duplicate title field Id')
            ids[key] = position
            target = Element('Content', position)
            fields(target, FOrientation=False, FontName=item.text('FontName', ''),
                   FontType=enum_value(item.value('TextShow', 'Text'), ('Text', 'Sheet', 'File')),
                   Align=enum_value(item.value('TextAlign', 'Left'), TEXT_ALIGN))
            read_lines(item, target)
            read_font(item, target, units=units)
            target.add('Placement', *point(item, units, ('X1', 'Y1'), 0), *point(item, units, ('X2', 'Y2'), 0))
            item.finish()
            contents.append(target)
        replace_rows(grid, 'Contents', contents)
        cells = []
        public_columns = source.rows('Cells', 'Item')
        if len(public_columns) != len(columns):
            raise ValueError(f'{source.node.path}: title columns do not match widths')
        for column, public in enumerate(public_columns):
            public_rows = public.children('Item')
            if len(public_rows) != len(rows):
                raise ValueError(f'{public.node.path}: title rows do not match heights')
            for row, item in enumerate(public_rows):
                key = item.integer('FieldId', -1)
                if key >= 0 and key not in ids:
                    raise ValueError(f'{item.node.path}: unresolved title field Id {key}')
                cell = Element('Cell', column, row, ids[key] if key >= 0 else key)
                cell.add('Edges', *(item.boolean(name, False) for name in ('TopLine', 'BottomLine', 'LeftLine', 'RightLine')))
                item.finish()
                cells.append(cell)
            public.finish()
        replace_rows(grid, 'Cells', cells)
        source.finish()


def read_tables(record, schematic, *, units, sheets):
    tables = []
    for index, source in enumerate(record.rows('Tables', 'Table')):
        source.integer('Id', index)  # Public drawing keys normalize to array order.
        sheet = source.integer('Sheet', 0)
        if sheet not in sheets:
            raise ValueError(f'{source.node.path}: unresolved sheet {sheet}')
        table = Element('Table')
        fields(table, Enabled=True, Selected=source.boolean('Selected', False),
               Locked=source.boolean('Locked', False), HideBorder=source.boolean('HideBorder', False),
               Page=sheets[sheet], Layer=0, Group=source.integer('Group', -1),
               Orientation=enum_value(source.number('Orientation', 0), ('0', '90', '180', '270')),
               DefAlign=enum_value(source.value('TextAlign', 'Left'), TEXT_ALIGN),
               DefFontName=source.text('FontName', ''), Name=source.text('Name', ''))
        for own, value in zip(('X1', 'Y1', 'X2', 'Y2'), (*point(source, units, ('X1', 'Y1'), 0),
                                                     *point(source, units, ('X2', 'Y2'), 0))):
            table.add(own, value)
        for public, own in (('CellWidth', 'DefCellWidth'), ('CellHeight', 'DefCellHeight')):
            table.add(own, length(source.number(public, 0), units))
        read_font(source, table, prefix='Def')
        columns, rows = _sizes(source, 'ColWidths', units), _sizes(source, 'RowHeights', units)
        for name, values in (('ColWidths', columns), ('RowHeights', rows)):
            parent = table.add(name)
            for value in values:
                parent.append(value)
        cells = table.add('Cells')
        public_columns = source.rows('Cells', 'Cell')
        if len(public_columns) != len(columns):
            raise ValueError(f'{source.node.path}: table columns do not match widths')
        for column in public_columns:
            public_rows = column.children('Cell')
            if len(public_rows) != len(rows):
                raise ValueError(f'{column.node.path}: table rows do not match heights')
            for item in public_rows:
                cell = cells.add('Cell', *point(item, units, ('X1', 'Y1'), 0), *point(item, units, ('X2', 'Y2'), 0))
                fields(cell, FOrientation=False, FontType=0,
                       Align=enum_value(item.value('TextAlign', 'Left'), TEXT_ALIGN), FontName=item.text('FontName', ''))
                read_lines(item, cell)
                read_font(item, cell)
                item.finish()
            column.finish()
        source.finish()
        tables.append(table)
    replace_rows(schematic, 'Tables', tables)
