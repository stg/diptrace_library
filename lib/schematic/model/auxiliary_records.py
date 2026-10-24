"""Named supporting records for groups, suppliers and model placement."""
from ...common.schema import Child, Field, Record, MISSING
from .field_groups import group


LOCAL_GROUP = group('LocalGroup', (
    Field('Enabled', 'boolean', required=True, default=True),
    Field('Id', 'integer', required=True, default=0,
          description='Stored local group code, independent of collection position.'),
    Field('X', 'number', required=True, default=0, unit='shared length'),
    Field('Y', 'number', required=True, default=0, unit='shared length'),
))
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
SUPPLIERS = Record('Suppliers', {
    name: Field(name, kind, default=default) for name, kind, default in (
        ('PartNumber', 'text', ''), ('Manufacturer', 'text', ''), ('Pattern', 'text', ''),
        ('Supplier', 'text', ''), ('SourceLocator', 'text', ''), ('Currency', 'text', ''),
        ('MainSupplier', 'boolean', MISSING))
}, children={'Prices': Child('Prices', 'Prices')})
MODEL3D = Record('Model3D', {
    name: Field(name, kind, default=default) for name, kind, default in (
        ('Model3DFile', 'text', ''), ('Model3DFile_Variable', 'text', ''),
        ('Mirror', 'boolean', False), ('NoSearch', 'boolean', False), ('Units', 'integer', 0),
        ('IPC_XOff', 'number', 0), ('IPC_YOff', 'number', 0), ('AutoHeight', 'number', 0),
        ('AutoColor', 'integer', 0x4B4B4B), ('Type', 'integer', 0), ('KeepPins', 'boolean', False))
}, children={name: Child(name, 'Model'+name) for name in ('Offset', 'Rotate', 'Zoom')})
VECTORS = {name: Record('Model'+name, {
    axis: Field(axis, 'number', required=True, default=1 if name == 'Zoom' else 0,
                description='Model '+name.lower()+' on this axis.') for axis in ('X', 'Y', 'Z')
}) for name in ('Offset', 'Rotate', 'Zoom')}
CACHE = Record('CacheLibrary', {}, children={
    name: Child(name, record) for name, record in (
        ('Categories', 'Categories'), ('PatternCategories', 'Categories'), ('Subfolders', 'Subfolders'),
        ('Slots', 'Slots'), ('Patterns', 'Patterns'), ('PadStyles', 'PadStyles'))
})
