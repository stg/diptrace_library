"""Assembly variants, generated-table settings and panelization data."""
from .preamble import _fields


def _table_settings(reader, table):
    rows = reader.add(table, 'RowComponents')
    for row_index in range(reader.count('table component rows')):
        row = reader.add(rows, 'Row', row_index)
        for _ in range(reader.count('components in table row')):
            reader.record(row, 'Item', 'integer')
    settings = reader.add(table, 'AutoUpdate')
    _fields(reader, settings, 'integer', 'AssemblyVariant RowType')
    _fields(reader, settings, 'number', 'PickOffX PickOffY')
    _fields(reader, settings, 'boolean', 'Header BomRowNumber BomTotal PickMirror PickOrigin')
    _fields(reader, settings, 'text', 'AssemblyName Separator')
    columns = reader.add(settings, 'Columns')
    for index in range(reader.count('documentation table columns')):
        column = reader.add(columns, 'Column', index)
        _fields(reader, column, 'integer', 'Type TextAlign')
        reader.field_into(column, 'Width', 'number')
        reader.field_into(column, 'Name', 'text')


def _panel_settings(reader, board):
    panel = reader.add(board, 'Panel')
    reader.field_into(panel, 'Type', 'integer')
    _fields(reader, panel, 'number', 'TabWidth TabRadius TabStep HoleDiam HoleStep HoleInset HoleKeepout')
    reader.field_into(panel, 'TabsDone', 'boolean')
    for name in ('HorzTabsX', 'VertTabsY'):
        positions = reader.add(panel, name)
        for _ in range(reader.count('panel tab positions')):
            reader.record(positions, 'Item', 'number')
    reader.field_into(panel, 'CombinedRadius', 'number')
    reader.field_into(panel, 'KeepMaterial', 'boolean')
    reader.field_into(panel, 'BorderTabs', 'integer')


def read_project_extensions(reader, board, cached_definitions):
    if reader.header.version <= 49:
        reader.add_into(board, 'CompRotate', True)
        return
    variants = reader.add(board.one('Settings'), 'AssemblyVariants')
    for _ in range(reader.count('assembly variants')):
        reader.record(variants, 'AssemblyVariant', 'text')
    for component in board.select('Components/Component'):
        excluded = reader.add(component, 'AssemblyExclude')
        for _ in range(reader.count('component assembly exclusions')):
            reader.record(excluded, 'Item', 'integer')
    for table in board.select('Tables/Table'):
        _table_settings(reader, table)
    for shape in board.select('Shapes/Shape'):
        reader.field_into(shape, 'PictureRaster', 'boolean')
        reader.field_into(shape, 'Picture_File', 'text')
        reader.field_into(shape, 'RasterIndex', 'integer')
        reader.field_into(shape, 'PictureTransparent', 'number')
    reader.field_into(board, 'CompRotate', 'boolean')
    _panel_settings(reader, board)
    for component in board.select('Components/Component'):
        reader.field_into(component.one('Pattern/Model3D'), 'KeepPins', 'boolean')
    for cached in cached_definitions:
        reader.field_into(cached.definition.one('Pattern/Model3D'), 'KeepPins', 'boolean')
