"""Assembly variants, generated-table settings and panelization data."""
from .preamble import _fields


def _table_settings(reader, table):
    rows = table.add('RowComponents')
    for row_index in range(reader.count('table component rows')):
        row = rows.add('Row', row_index)
        for _ in range(reader.count('components in table row')):
            reader.record(row, 'Item', 'integer')
    settings = table.add('AutoUpdate')
    _fields(reader, settings, 'integer', 'AssemblyVariant RowType')
    _fields(reader, settings, 'number', 'PickOffX PickOffY')
    _fields(reader, settings, 'boolean', 'Header BomRowNumber BomTotal PickMirror PickOrigin')
    _fields(reader, settings, 'text', 'AssemblyName Separator')
    columns = settings.add('Columns')
    for index in range(reader.count('documentation table columns')):
        column = columns.add('Column', index)
        _fields(reader, column, 'integer', 'Type TextAlign')
        reader.field(column, 'Width', 'number')
        reader.field(column, 'Name', 'text')


def _panel_settings(reader, board):
    panel = board.add('Panel')
    reader.field(panel, 'Type', 'integer')
    _fields(reader, panel, 'number', 'TabWidth TabRadius TabStep HoleDiam HoleStep HoleInset HoleKeepout')
    reader.field(panel, 'TabsDone', 'boolean')
    for name in ('HorzTabsX', 'VertTabsY'):
        positions = panel.add(name)
        for _ in range(reader.count('panel tab positions')):
            reader.record(positions, 'Item', 'number')
    reader.field(panel, 'CombinedRadius', 'number')
    reader.field(panel, 'KeepMaterial', 'boolean')
    reader.field(panel, 'BorderTabs', 'integer')


def read_project_extensions(reader, board, cached_definitions):
    if reader.header.version <= 49:
        board.add('CompRotate', True)
        return
    variants = board.one('Settings').add('AssemblyVariants')
    for _ in range(reader.count('assembly variants')):
        reader.record(variants, 'AssemblyVariant', 'text')
    for component in board.select('Components/Component'):
        excluded = component.add('AssemblyExclude')
        for _ in range(reader.count('component assembly exclusions')):
            reader.record(excluded, 'Item', 'integer')
    for table in board.select('Tables/Table'):
        _table_settings(reader, table)
    for shape in board.select('Shapes/Shape'):
        reader.field(shape, 'PictureRaster', 'boolean')
        reader.field(shape, 'Picture_File', 'text')
        reader.field(shape, 'RasterIndex', 'integer')
        reader.field(shape, 'PictureTransparent', 'number')
    reader.field(board, 'CompRotate', 'boolean')
    _panel_settings(reader, board)
    for component in board.select('Components/Component'):
        reader.field(component.one('Pattern/Model3D'), 'KeepPins', 'boolean')
    for cached in cached_definitions:
        reader.field(cached.definition.one('Pattern/Model3D'), 'KeepPins', 'boolean')
