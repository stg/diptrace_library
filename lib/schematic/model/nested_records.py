"""Named nested records using the established public schematic vocabulary."""
from ...common.schema import Field, Record
from .field_groups import group, POINT, SHOW, ALIGN


WIRE_POINT = group('WirePoint', (*POINT.fields.values(),
    Field('Dir', 'integer', required=True, default=0,
          description='Stored wire/bus routing direction code.'),
))
CATEGORY_TYPE = group('CategoryType', (
    Field('Type', 'text', required=True, default='', description='Classification type name.'),
    Field('SubType', 'text', required=True, default='', description='Classification subtype name.'),
    Field('TypeIndex', 'integer', required=True, default=-1, description='Declared type key.'),
    Field('SubTypeIndex', 'integer', required=True, default=-1, description='Declared subtype key.'),
))
CATALOG_ENTRY = group('CatalogEntry', (
    Field('Name', 'text', required=True, default=''),
    Field('Index', 'integer', required=True, default=-1,
          description='Declared catalog key; independent of collection position.'),
))
LIBRARY_PATH = Record('LibraryPath', {
    'Path': Field('Path', 'text', required=True, default=''),
    'VariablePath': Field('VariablePath', 'text', default=''),
}, ('Path',))
SUBFOLDER = group('LibrarySubfolder', (Field('Name', 'text', required=True, default=''),))
POSSIBLE_NAME = group('PossibleName', (Field('Name', 'text', required=True, default=''),))
MODEL_LINE = group('ModelLine', (Field('Text', 'text', required=True, default=''),))
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
PASTE_SEGMENT = group('PasteSegment', tuple(
    Field(name, 'number', required=True, default=0, unit='shared length')
    for name in ('X1', 'Y1', 'X2', 'Y2')
))
TERMINAL_COUNT = Field('PadTerminalCount', 'integer', getter=lambda owner: len(owner._child_sequence('PadTerminal')),
                       collection_dependencies=lambda owner: ((owner, 'PadTerminal'),),
                       description='Calculated number of current terminal records.')
TERMINAL = Record('PadTerminal', {
    'Index': Field('Index', 'integer', getter=lambda terminal: terminal._ordinal(),
                    ordinal_dependencies=lambda terminal: (terminal,),
                    description='Current terminal position.'),
    'Type': Field('Type', 'integer|text', required=True, default=0,
                   description='Terminal shape code or a public text selection, including empty text.'),
    'Angle': Field('Angle', 'number', required=True, default=0,
                    description='Unquantized terminal angle in its public field representation.'),
    **{name: Field(name, 'number', required=True, default=0, unit='shared length')
       for name in ('X', 'Y', 'ShapeWidth', 'ShapeHeight')},
    'ShapeCorner': Field('ShapeCorner', 'number', required=True, default=0, unit='percent'),
}, ('Index',))
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
