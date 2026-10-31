"""Schematic hierarchy linkage recorded by a PCB document.

These identifiers describe the linked schematic. They are persistent keys,
not positions in this PCB's component or electrical-connection collections.
"""
from ...common.schema import Child, Field, Record


PATH_ITEM = Record('SchematicHierarchyPathItem', {
    'Id': Field('Id', 'integer', required=True,
                description='Referenced schematic hierarchy-block identifier; linked when its block is available.'),
}, parameters=('Id',))
PATH = Record('SchematicHierarchyPath', {}, children={
    'Item': Child('Item', PATH_ITEM.name, maximum=None),
})
BLOCK = Record('SchematicHierarchyBlock', {
    'Id': Field('Id', 'integer', required=True),
    'Name': Field('Name', 'text', required=True, default=''),
}, parameters=('Id', 'Name'))
BLOCKS = Record('SchematicHierarchyBlocks', {}, children={
    'UId': Child('UId', BLOCK.name, maximum=None),
})
SHEET = Record('SchematicHierarchySheet', {
    'Name': Field('Name', 'text', required=True, default=''),
    'Number': Field('Number', 'integer', required=True,
                    description='Linked schematic sheet identifier, independent of PCB order.'),
}, parameters=('Name', 'Number'), children={'UpdateIds': Child('UpdateIds', BLOCKS.name)})
SHEETS = Record('SchematicHierarchySheets', {}, children={
    'HSheet': Child('HSheet', SHEET.name, maximum=None),
})


def definition(node):
    parent = node.parent
    if parent is None:
        return None
    if parent.kind == 'Component' and node.kind == 'HierarchyPath':
        return PATH
    if parent.kind == 'HierarchyPath' and node.kind == 'Item':
        return PATH_ITEM
    if parent.kind == 'Board' and node.kind == 'HierarchySheets':
        return SHEETS
    if parent.kind == 'HierarchySheets' and node.kind == 'HSheet':
        return SHEET
    if parent.kind == 'HSheet' and node.kind == 'UpdateIds':
        return BLOCKS
    if parent.kind == 'UpdateIds' and node.kind == 'UId':
        return BLOCK
    return None
