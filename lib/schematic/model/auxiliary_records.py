"""Named supporting records for groups, suppliers and model placement."""
from ...common.schema import Field, Record
from ...common.footprint_records import SUPPLIERS, MODEL3D, VECTORS
from ...common.group_records import LOCAL_GROUP
from .field_groups import group


SCHEMATIC_GROUP = Record('SchematicGroup', {
    'Index': Field('Index', 'integer', required=True, default=0, description='Managed group index.'),
    'Enabled': Field('Enabled', 'boolean', required=True, default=True),
    'Selected': Field('Selected', 'boolean', required=True, default=False),
    'X': Field('X', 'number', required=True, default=0, unit='shared length'),
    'Y': Field('Y', 'number', required=True, default=0, unit='shared length'),
}, ('Index', 'X', 'Y'))
BUS_NUMBER = group('BusNumber', (Field('Number', 'integer', required=True, default=0),))
BUS_NET = group('BusNet', (Field('NetIndex', 'integer', required=True, default=-1,
                               description='Managed index of a bus member net.'),))
UNRESOLVED_MEMBER = group('UnresolvedNetMember', (
    Field('PartIndex', 'integer', required=True, default=-1),
    Field('PinIndex', 'integer', required=True, default=-1),
))
UNRESOLVED_KEY = group('UnresolvedKey', (
    Field('Field', 'text', required=True, default='', description='Name of the unresolved relationship field.'),
    Field('Id', 'integer', required=True, default=0, description='Unresolved public target key.'),
))
