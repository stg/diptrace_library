"""PCB XML grids and documentation settings over the shared editable cells."""
from ....common.cell_text import modernize_cell_text
from ....common.xml_cells import read_lines, read_table_grid
from ....common.xml_font_import import read_font, read_text_extent
from ....common.xml_records import enum_value, length
from ....common.title_records import TEXT_ALIGN
from .font import read_width


LAYERS = ('Top Assy', 'Top Silk', 'Bottom Silk', 'Bottom Assy', 'Non-Signal')
DOCUMENT_TYPES = ('Text', 'LayerStack', 'BOM', 'Pick and Place', 'Hole Size')
UNITS = ('Common', 'inch', 'mil', 'mm')
COMPONENT_ROWS = ('Components', 'Name', 'Name and Value', 'Name and Pattern', 'Name, Value and Pattern')
PLACEMENT_ROWS = ('All', 'Top', 'Bottom')
DEFAULT_CELL_WIDTH, DEFAULT_CELL_HEIGHT = 45, 12


def _font(source, target, *, units, version, prefix='', defaults=False):
    read_font(source, target, prefix=prefix, size=prefix+'FontSize', default=8 if defaults else 0)
    target.add(prefix+'VectorFont', source.boolean('FontVector', defaults))
    target.add(prefix+'FontName', source.text('FontName', 'Tahoma' if defaults else ''))
    target.add(prefix+'FontWidth', read_width(source, units=units, version=version, default=-2 if defaults else 0))
    target.add(prefix+'FontScale', source.number('FontScale', 1 if defaults else 0))
    spacing = source.number('LineSpacing', 1.2 if defaults else 0)
    target.add(prefix+'LineSpacing', length(spacing, units) if not defaults and version.legacy_cell_line_spacing else spacing)
    target.add(prefix+'FontColor', 0)
    read_text_extent(source)


def _settings(source, table, *, units, version):
    update = table.add('AutoUpdate')
    kind = enum_value(source.value('Type', 'Text'), DOCUMENT_TYPES) if source is not None else 0
    table.add('DocType', kind)
    table.add('DocUnits', enum_value(source.value('Units', 'Common'), UNITS) if source is not None else 0)
    update.add('AssemblyVariant', source.integer('AssemblyVariant', 0) if source is not None else 0)
    update.add('RowType', enum_value(source.value('RowType', 0), PLACEMENT_ROWS if kind == 3 else COMPONENT_ROWS)
               if source is not None else 0)
    for name in ('Header', 'BomRowNumber', 'BomTotal', 'PickMirror', 'PickOrigin'):
        update.add(name, source.boolean(name, False) if source is not None else False)
    for name in ('PickOffX', 'PickOffY'):
        value = source.number(name, 0) if source is not None else 0
        update.add(name, length(value, units, reverse=name == 'PickOffY' and version.legacy_table_pickoff_y))
    for name, default in (('AssemblyName', ''), ('Separator', '')):
        update.add(name, source.text(name, default) if source is not None else default)
    table.add('Supplier', source.text('Supplier', '') if source is not None else '')
    columns = update.add('Columns')
    if source is not None:
        for index, item in enumerate(source.rows('Columns', 'Column')):
            column = columns.add('Column', index)
            column.add('Type', item.integer('Type', 0))
            column.add('TextAlign', enum_value(item.value('TextAlign', 'Left'), TEXT_ALIGN))
            column.add('Width', length(item.number('Width', 0), units))
            column.add('Name', item.text('Name', ''))
            column.add('Title', item.text('Title', ''))
            item.finish()
        source.finish()


def read_tables(record, board, *, units, version):
    tables = board.add('Tables')
    for index, source in enumerate(record.rows('Tables', 'Table')):
        source.integer('Id', index)  # Output counter; relationships use current table identity.
        table = tables.add('Table', index)
        for name, default in (('Enabled', True), ('Selected', False), ('Locked', False),
                              ('HideBorder', False), ('PanelExclude', False)):
            table.add(name, source.boolean(name, default))
        table.add('Layer', enum_value(source.value('Layer', 'Top Assy'), LAYERS))
        table.add('NonSignal', source.integer('NonSignal', 0))
        table.add('Group', source.integer('Group', -1))
        table.add('Orientation', enum_value(source.value('Orientation', '0'), ('0', '90', '180', '270')))
        table.add('DefAlign', enum_value(source.value('TextAlign', 'Left'), TEXT_ALIGN))
        table.add('Name', source.text('Name', 'Table'))
        for name, default in (('CellWidth', DEFAULT_CELL_WIDTH), ('CellHeight', DEFAULT_CELL_HEIGHT)):
            table.add('Def'+name, length(source.number(name), units) if source.has(name) else default)
        for name, default in (('X1', 0), ('Y1', 0), ('X2', 2*DEFAULT_CELL_WIDTH), ('Y2', 2*DEFAULT_CELL_HEIGHT)):
            table.add(name, length(source.number(name), units, reverse=name.startswith('Y'))
                      if source.has(name) else default)
        _font(source, table, prefix='Def', units=units, version=version, defaults=True)
        _settings(source.take('AutoUpdate'), table, units=units, version=version)
        rows = table.add('RowComponents')
        for row_index, row in enumerate(source.rows('RowComponents', 'RowCom')):
            target = rows.add('Row', row_index)
            for member in row.children('Item'):
                value = member.content()
                if value.kind != 'number' or value.unit or type(value.value) is not int:
                    raise ValueError(f'{member.node.path}: expected a component position')
                target.add('Item', value)
                member.finish(allow_text=True)
            row.finish()

        def read_cell(item, cell):
            cell.add('FOrientation', False)
            cell.add('FontType', 0)
            cell.add('Align', enum_value(item.value('TextAlign', 'Left'), TEXT_ALIGN))
            _font(item, cell, units=units, version=version)
            read_lines(item, cell)

        read_table_grid(source, table, units=units, read_cell=read_cell)
        source.finish()
    modernize_cell_text(board, paths=('Tables/Table/Cells/Cell',))
