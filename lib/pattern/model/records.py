"""Standalone pattern authoring metadata around shared editable footprints."""
from dataclasses import replace

from ...common import library_metadata
from ...common import library_catalogue as catalogue
from ...common.supplier_records import SUPPLIERS
from ...common.schema import Child, Field, Record
from ...common import unplaced_footprint_records as physical
from ...common.unplaced_footprint_records import (
    GROUP_ROLE, PAD_ROLE, DIMENSION_ROLES, CONNECTION_ROLES, GROUP, GROUPS, PAD, DRAWING, HOLE,
    DIMENSION, PADS, DRAWINGS, HOLES, DIMENSIONS, PAIR, CONNECTIONS)


PATTERN = replace(physical.PATTERN, fields={**physical.PATTERN.fields,
    'Category': catalogue.CATEGORY,
    **{name: replace(physical.PATTERN.fields[name], setter=lambda source, value, key=name.endswith('Index'):
            catalogue.assign_scalar(source, value, catalogue.CATEGORY_ROLE, key=key))
       for name in ('Pattern_CategoryName', 'Pattern_CategoryIndex')},
    'Value': Field('Value', 'text', description='Default value of this unplaced pattern.'),
    'Verification': Field('Verification', 'tuple', required=True, default=(False,)*4,
                          item_kind='boolean', length=4,
                          description='Four saved pattern verification states.')},
    children={**physical.PATTERN.children, 'Suppliers': Child('Suppliers', SUPPLIERS.name),
              'Pattern_CategoryTypes': Child('Pattern_CategoryTypes', catalogue.CLASSIFICATION_ROWS.name)})
PATTERNS = Record('Patterns', {}, children={'Pattern': Child('Pattern', PATTERN.name, maximum=None)})
LIBRARY = Record('PatternLibrary', {
    'Name': Field('Name', 'text', required=True, default='Library'),
    'Hint': Field('Hint', 'text', required=True, default='Untitled Library'),
}, children={'Categories': Child('Categories', library_metadata.CATEGORIES.name),
             'Patterns': Child('Patterns', PATTERNS.name)})
DOCUMENT = Record('PatternDocument', {}, children={'Library': Child('Library', LIBRARY.name, minimum=1)})
