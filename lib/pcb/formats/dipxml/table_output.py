"""Current PCB documentation tables, grids and component-row relationships."""
from ....common.conversion import warn
from ....common.model import Element
from ....common.title_records import TEXT_ALIGN
from ....common.xml import set_attribute
from ....common.xml_cell_output import append_table_grid, bounds, font, text_lines
from ....common.xml_output import enum_text, field, numeric
from ...model import table_records
from ..errors import PcbError
from ..output_indices import non_signal_number
from ..output_validation import check_tree, field_value
from .tables import LAYERS, DOCUMENT_TYPES, UNITS, COMPONENT_ROWS, PLACEMENT_ROWS


def _font(source, target, *, units, prefix='', physical_font_width=True, legacy_spacing=False, report):
    font(source, target, prefix=prefix, units=units if physical_font_width else None, color=False)
    if legacy_spacing:
        set_attribute(target, 'LineSpacing', numeric(units.length(source[prefix+'LineSpacing'])))
    field(target, 'FontName', source[prefix+'FontName'])
    if source.get(prefix+'FontColor', 0) != 0:
        warn(report, 'table-font-color', 'dipxml', 'XML table fonts omit independent text colors', (source,))


def _settings(table, *, units):
    source, target = table.one('AutoUpdate'), Element('AutoUpdate')
    for name, value in (('Type', enum_text(table['DocType'], DOCUMENT_TYPES)),
                        ('Units', enum_text(table['DocUnits'], UNITS)),
                        ('RowType', enum_text(source['RowType'], PLACEMENT_ROWS if table['DocType'] == 3 else COMPONENT_ROWS))):
        set_attribute(target, name, value)
    for name in ('AssemblyVariant', 'Header', 'BomRowNumber', 'BomTotal', 'PickMirror', 'PickOrigin'):
        set_attribute(target, name, source[name])
    for name in ('PickOffX', 'PickOffY'):
        set_attribute(target, name, numeric(units.length(source[name])))
    for name in ('AssemblyName', 'Separator'):
        field(target, name, source[name])
    field(target, 'Supplier', table['Supplier'])
    columns = target.add('Columns')
    for column in source.select('Columns/Column'):
        row = columns.add('Column')
        set_attribute(row, 'Type', column['Type'])
        set_attribute(row, 'TextAlign', enum_text(column['TextAlign'], TEXT_ALIGN))
        set_attribute(row, 'Width', numeric(units.length(column['Width'])))
        for name in ('Name', 'Title'):
            field(row, name, field_value(column, name, destination='DIPXML'))
    return target


def project_tables(board, *, units, physical_font_width=True, legacy_cell_spacing=False, report=None):
    result = Element('Tables')
    for table in board.select('Tables/Table'):
        check_tree(table, table_records.TABLE, destination='DIPXML')
        if not field_value(table, 'Enabled'):
            raise PcbError(f'{table.path}: inactive table needs output normalization')
        row = result.add('Table')
        set_attribute(row, 'Id', table['Id'])
        bounds(row, tuple(table[name] for name in ('X1', 'Y1', 'X2', 'Y2')), units)
        for name, value in (('Layer', enum_text(table['Layer'], LAYERS)),
                            ('NonSignal', non_signal_number(table, destination='dipxml', report=report)),
                            ('Orientation', int(enum_text(table['Orientation'], ('0', '90', '180', '270')))),
                            ('Group', table['GroupId']), ('TextAlign', enum_text(table['DefAlign'], TEXT_ALIGN))):
            set_attribute(row, name, value)
        for name in ('HideBorder', 'PanelExclude', 'Locked', 'Selected'):
            set_attribute(row, name, field_value(table, name))
        for name in ('CellWidth', 'CellHeight'):
            set_attribute(row, name, numeric(units.length(table['Def'+name])))
        _font(table, row, units=units, prefix='Def', physical_font_width=physical_font_width, report=report)
        field(row, 'Name', table['Name'])
        row.append(_settings(table, units=units))
        members = row.add('RowComponents')
        for source in table.select('RowComponents/Row'):
            target = members.add('RowCom')
            for member in source.children('Item'):
                if member.child('UnresolvedComponentIndex') is not None:
                    warn(report, 'unresolved-table-component', 'dipxml',
                         'Table row retains a component position without a current target', (member,))
                field(target, 'Item', member['ComponentIndex'])

        def project_cell(source, target):
            set_attribute(target, 'TextAlign', enum_text(source['Align'], TEXT_ALIGN))
            _font(source, target, units=units, physical_font_width=physical_font_width,
                  legacy_spacing=legacy_cell_spacing, report=report)
            text_lines(source, target)
            if source['FOrientation'] or source['FontType'] != 0:
                warn(report, 'table-cell-text-mode', 'dipxml',
                     'XML table cells carry literal text without separate text orientation or calculated text mode', (source,))

        append_table_grid(table, row, units=units, project_cell=project_cell)
    return result
