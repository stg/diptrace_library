"""PCB title grids share their physical fields and styled text with schematics."""
from dataclasses import replace

from ...common import title_records as shared
from ...common import cell_records
from ...common.schema import Child, Field, Record
from . import title_relations as links


CONTENT = shared.TITLE_FIELD
CELL = replace(shared.TITLE_CELL, name='PcbTitleCell', fields={
    **shared.TITLE_CELL.fields,
    'Field': Field('Field', 'reference', nullable=True, getter=links.field, setter=links.set_field,
                   reference_dependencies=links.dependencies, value_dependencies=links.values,
                   collection_dependencies=links.collections),
    'FieldId': Field('FieldId', 'integer', getter=links.field_id,
        reference_dependencies=links.dependencies, ordinal_dependencies=links.ordinals,
        value_dependencies=links.values, collection_dependencies=links.collections),
    links.MISSING: Field(links.MISSING, 'integer', description='An unavailable supplied title-field selection.'),
})
CELLS = Record('PcbTitleCells', {}, children={'Cell': Child('Cell', CELL.name, maximum=None)})
CONTENTS = Record('PcbTitleFields', {}, children={'Content': Child('Content', CONTENT.name, maximum=None)})
BLOCK = replace(shared.TITLE_BLOCK, name='PcbTitleBlock', children={
    'Cells': Child('Cells', CELLS.name), 'Contents': Child('Contents', CONTENTS.name),
    'ColWidths': Child('ColWidths', cell_records.COLUMN_WIDTHS.name),
    'RowHeights': Child('RowHeights', cell_records.ROW_HEIGHTS.name),
})
BLOCKS = Record('PcbTitleBlocks', {}, children={'TitleBlock': Child('TitleBlock', BLOCK.name, maximum=6)})


def definition(node):
    parent = node.parent
    owner = parent.parent if parent is not None else None
    if parent is not None and parent.kind == 'SheetSettings' and node.kind == 'TitleBlocks':
        return BLOCKS
    if parent is not None and parent.kind == 'TitleBlocks' and node.kind == 'TitleBlock':
        return BLOCK
    if parent is not None and parent.kind == 'TitleBlock':
        return {'Cells': CELLS, 'Contents': CONTENTS, 'ColWidths': cell_records.COLUMN_WIDTHS,
                'RowHeights': cell_records.ROW_HEIGHTS}.get(node.kind)
    if owner is not None and owner.kind == 'TitleBlock':
        return {('Cells', 'Cell'): CELL, ('Contents', 'Content'): CONTENT,
                ('ColWidths', 'pt'): cell_records.COLUMN_WIDTH,
                ('RowHeights', 'pt'): cell_records.ROW_HEIGHT}.get((parent.kind, node.kind))
    if parent is not None and links.grid_of(parent) is not None:
        if parent.kind == 'Cell' and node.kind == 'Edges':
            return shared.BORDERS
        if parent.kind == 'Content' and node.kind == 'Placement':
            return cell_records.BOUNDS
    return None
