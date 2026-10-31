"""Public XML table grids and page title blocks from owned data."""
from ....common.title_records import TEXT_ALIGN
from .syntax import (set_attribute)
from ....common.xml_output import enum_text, field, numeric
from ....common.model import (Element)
from ....common.xml_cell_output import (bounds as _bounds, text_lines as _text, font as _project_font,
                                        append_table_grid,
                                        project_title_block as _project_title_block,
                                        append_title_blocks as _append_title_blocks)


def _font(source, target, *, prefix='', units=None, version=46):
    _project_font(source, target, prefix=prefix, units=units, fractional_font=version >= 52)


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
    def project_cell(source, item):
        set_attribute(item, 'TextAlign', enum_text(source.scalar('Align'), TEXT_ALIGN))
        field(item, 'FontName', source.scalar('FontName'))
        _text(source, item)
        _font(source, item, version=version)
    append_table_grid(table, result, units=units, project_cell=project_cell)
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
    return _project_title_block(grid, name=name, units=units, fractional_font=version >= 52)


def append_title_blocks(page, sheet, *, units, version=46):
    _append_title_blocks(page, sheet, units=units, fractional_font=version >= 52)
