"""Named nested records using the established public schematic vocabulary."""
from ...common.schema import Field
from ...common.footprint_records import TERMINAL, TERMINAL_COUNT, PASTE_SEGMENT
from ...common.library_metadata import (CATEGORY_TYPE, CATALOG_ENTRY, LIBRARY_PATH,
                                        SUBFOLDER, POSSIBLE_NAME, MODEL_LINE)
from .field_groups import group, POINT, SHOW, ALIGN


WIRE_POINT = group('WirePoint', (*POINT.fields.values(),
    Field('Dir', 'integer', required=True, default=0,
          description='Stored wire/bus routing direction code.'),
))
GLOBAL_USER_FIELD = group('GlobalUserField', (
    Field('Name', 'text', required=True, default='', description='Display name.'),
    Field('Value', 'text', required=True, default='', description='User-field lookup key.'),
    SHOW, ALIGN,
))
INTERNAL_CONNECTION = group('InternalConnection', (
    Field('X', 'integer', required=True, default=0, description='First pad index; not a coordinate.'),
    Field('Y', 'integer', required=True, default=0, description='Second pad index; not a coordinate.'),
))
QUOTE = group('Quote', (
    Field('Quantity', 'integer', required=True, default=0),
    Field('Price', 'number', required=True, default=0, description='Unit price in the supplier currency.'),
))
DIFFERENTIAL_PAIR = group('DifferentialPair', (
    Field('Name', 'text', required=True, default=''),
    Field('Enabled', 'boolean', required=True, default=True),
    Field('PosNet', 'integer', required=True, default=-1, description='Managed positive net index.'),
    Field('NegNet', 'integer', required=True, default=-1, description='Managed negative net index.'),
    Field('NetClass', 'integer', required=True, default=-1, description='Managed net-class index.'),
    Field('CustomColor', 'boolean', required=True, default=False),
    Field('WireColor', 'integer', required=True, default=0),
))


def modernize_classifications(schematic):
    """Use one row kind for cached, placed and public XML classifications."""
    for node in schematic.walk(include_self=True):
        if (node.kind in ('Type', 'Component_Type', 'Pattern_Type') and node.parent is not None and
                node.parent.kind in ('Component_CategoryTypes', 'Pattern_CategoryTypes')):
            node.kind = 'CategoryType'
