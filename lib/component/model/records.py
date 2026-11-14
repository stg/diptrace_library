"""Standalone component ownership over shared symbol and physical definitions.

Component descriptions have one owner. Values, simulation and symbol geometry
belong to individual parts; their descriptive accessors refer to that owner.
"""
from dataclasses import replace

from ...common import library_metadata, symbol_records
from ...common import library_catalogue as catalogue
from ...common import unplaced_footprint_records as physical
from ...common.schema import Child, Field, Record
from ...common.supplier_records import SUPPLIERS
from ...common.user_fields import USER_FIELDS
from ...common.relationship_fields import optional_reference_fields
from .metadata import SHARED_FIELDS, shared_field, FOLDER_ROLE
from . import symbols


PART = replace(symbol_records.SYMBOL, name='LibraryPart', parameters=(), fields={
    **{name: field for name, field in symbol_records.SYMBOL.fields.items()
       if name not in (*SHARED_FIELDS, 'ModelNote')},
    **{name: shared_field(name, 'integer' if name.endswith('Index') else 'text',
                          default=-1 if name.endswith('Index') else '') for name in SHARED_FIELDS},
}, children={
    **{name: child for name, child in symbol_records.SYMBOL.children.items()
       if name not in ('Component_CategoryTypes', 'UserFields', 'Suppliers')},
    'Pins': Child('Pins', symbols.PINS.name),
    'Shapes': Child('Shapes', symbols.DRAWINGS.name),
    'Groups': Child('Groups', physical.GROUPS.name),
})
PARTS = Record('LibraryParts', {}, children={'Part': Child('Part', PART.name, minimum=1, maximum=None)})
COMPONENT = Record('LibraryComponent', {
    **{name: Field(name, 'text', required=True, default='') for name in
       ('Name', 'RefDes', 'Manufacturer', 'Datasheet')},
    'Category': catalogue.CATEGORY,
    **{name: Field(name, 'integer' if name.endswith('Index') else 'text', required=True,
                  default=-1 if name.endswith('Index') else '',
                  setter=lambda source, value, key=name.endswith('Index'):
                      catalogue.assign_scalar(source, value, catalogue.CATEGORY_ROLE, key=key))
       for name in ('Component_CategoryName', 'Component_CategoryIndex')},
    **optional_reference_fields('Folder', 'SubfolderIndex', FOLDER_ROLE),
}, children={
    'Parts': Child('Parts', PARTS.name, minimum=1),
    'Pattern': Child('Pattern', physical.PATTERN.name),
    'Component_CategoryTypes': Child('Component_CategoryTypes', catalogue.CLASSIFICATION_ROWS.name),
    'UserFields': Child('UserFields', USER_FIELDS.name),
    'Suppliers': Child('Suppliers', SUPPLIERS.name),
})
COMPONENTS = Record('LibraryComponents', {}, children={'Component': Child('Component', COMPONENT.name, maximum=None)})
LIBRARY = Record('ComponentLibrary', {
    'Name': Field('Name', 'text', required=True, default='Library'),
    'Hint': Field('Hint', 'text', required=True, default='Untitled Library'),
}, children={
    'Categories': Child('Categories', library_metadata.CATEGORIES.name),
    'Subfolders': Child('Subfolders', library_metadata.SUBFOLDERS.name),
    'Components': Child('Components', COMPONENTS.name),
})
DOCUMENT = Record('ComponentDocument', {}, children={'Library': Child('Library', LIBRARY.name, minimum=1)})
