"""Normalize public table grids and title fields into editable own records."""
from ....common.xml_records import (enum_value, length, point, replace_rows)
from ....common.title_records import TEXT_ALIGN
from ....common.xml_cells import read_font, read_lines, read_table_grid
from ....common.model import (Element)
from ...model.new import (fields)


def _read_cell(item, cell):
    fields(cell, FOrientation=False, FontType=0,
           Align=enum_value(item.value('TextAlign', 'Left'), TEXT_ALIGN), FontName=item.text('FontName', ''))
    read_lines(item, cell)
    read_font(item, cell)


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
        read_table_grid(source, table, units=units, read_cell=_read_cell)
        source.finish()
        tables.append(table)
    replace_rows(schematic, 'Tables', tables)
