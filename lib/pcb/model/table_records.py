"""PCB table grids and supplied documentation-generation settings."""
from ...common import cell_records as cells
from ...common.schema import Child, Field, Record, MISSING
from .graphic_records import GROUP_FIELDS
from .non_signal_layers import SELECTION_FIELDS
from . import table_relations as relations
from .assembly_variants import TABLE_FIELDS


def _fields(kind, names, default=MISSING):
    return {name: Field(name, kind, default=default) for name in names.split()}


UPDATE = Record('PcbTableUpdate', {
    **_fields('integer', 'RowType'), **TABLE_FIELDS,
    **_fields('number', 'PickOffX PickOffY'),
    **_fields('boolean', 'Header BomRowNumber BomTotal PickMirror PickOrigin'),
    **_fields('text', 'AssemblyName Separator'),
}, children={'Columns': Child('Columns', 'PcbTableUpdateColumns')})
COLUMN = Record('PcbTableUpdateColumn', {
    **_fields('integer', 'Type TextAlign'), **_fields('number', 'Width'),
    **{name: Field(name, 'text', default='') for name in ('Name', 'Title')},
    'Index': Field('Index', 'integer', getter=lambda node: node._ordinal(),
                    ordinal_dependencies=lambda node: (node,)),
}, parameters=('Index',))
MEMBER = Record('PcbTableRowComponent', {
    'Component': Field('Component', 'reference', nullable=True,
        getter=relations.component, setter=relations.set_component,
        reference_dependencies=relations.reference_dependencies,
        collection_dependencies=relations.collection_dependencies,
        value_dependencies=relations.value_dependencies),
    'ComponentIndex': Field('ComponentIndex', 'integer', getter=relations.component_index,
        reference_dependencies=relations.reference_dependencies,
        collection_dependencies=relations.collection_dependencies,
        value_dependencies=relations.value_dependencies,
        ordinal_dependencies=relations.ordinal_dependencies),
    'UnresolvedComponentIndex': Field('UnresolvedComponentIndex', 'integer',
        description='A supplied component position without a current target; absent for resolved members.'),
}, parameters=('ComponentIndex',))
ROW = Record('PcbTableComponentRow', {
    'Index': Field('Index', 'integer', getter=lambda node: node._ordinal(),
                    ordinal_dependencies=lambda node: (node,)),
}, parameters=('Index',), children={'Item': Child('Item', MEMBER.name, maximum=None)})
COLUMNS = Record('PcbTableUpdateColumns', {}, children={'Column': Child('Column', COLUMN.name, maximum=None)})
ROWS = Record('PcbTableComponentRows', {}, children={'Row': Child('Row', ROW.name, maximum=None)})
TABLE = Record('PcbTable', {
    'Id': Field('Id', 'integer', getter=lambda node: node._ordinal(),
                ordinal_dependencies=lambda node: (node,)), **GROUP_FIELDS,
    **_fields('boolean', 'Enabled Selected Locked DefVectorFont HideBorder PanelExclude DefFontMono', False),
    **_fields('integer', 'Layer DefAlign Orientation DefFontColor DocType DocUnits', 0), **SELECTION_FIELDS,
    **_fields('number', 'DefFontSize DefCellWidth DefCellHeight X1 Y1 X2 Y2 DefFontWidth DefFontScale DefLineSpacing', 0),
    **_fields('text', 'DefFontName Name Supplier', ''),
}, parameters=('Id',), children={
    'Cells': Child('Cells', cells.CELLS.name), 'ColWidths': Child('ColWidths', cells.COLUMN_WIDTHS.name),
    'RowHeights': Child('RowHeights', cells.ROW_HEIGHTS.name),
    'AutoUpdate': Child('AutoUpdate', UPDATE.name), 'RowComponents': Child('RowComponents', ROWS.name),
})


def definition(node):
    parent = node.parent
    owner = parent.parent if parent is not None else None
    if parent is None:
        return None
    if (node.kind == 'Table' and parent.kind == 'Tables' and owner is not None and owner.kind == 'Board'):
        return TABLE
    if parent.kind == 'Table':
        return {'Cells': cells.CELLS, 'ColWidths': cells.COLUMN_WIDTHS, 'RowHeights': cells.ROW_HEIGHTS,
                'AutoUpdate': UPDATE, 'RowComponents': ROWS}.get(node.kind)
    if owner is not None and owner.kind == 'Table':
        return {('Cells', 'Cell'): cells.CELL, ('ColWidths', 'pt'): cells.COLUMN_WIDTH,
                ('RowHeights', 'pt'): cells.ROW_HEIGHT, ('AutoUpdate', 'Columns'): COLUMNS,
                ('RowComponents', 'Row'): ROW}.get((parent.kind, node.kind))
    if parent.kind == 'Columns' and parent.parent is not None and parent.parent.kind == 'AutoUpdate':
        return COLUMN if node.kind == 'Column' else None
    if (parent.kind == 'Row' and owner is not None and owner.kind == 'RowComponents'
            and owner.parent is not None and owner.parent.kind == 'Table'):
        return MEMBER if node.kind == 'Item' else None
    return None
