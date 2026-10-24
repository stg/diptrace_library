"""Named library records shared by placed footprints and cached definitions."""
from ...common.schema import Field, Record


HOLE = Record('Hole', {
    'Enabled': Field('Enabled', 'boolean', required=True, default=False),
    'Locked': Field('Locked', 'boolean', required=True, default=False),
    'X': Field('X', 'number', required=True, default=0, unit='shared length'),
    'Y': Field('Y', 'number', required=True, default=0, unit='shared length'),
    'Diam': Field('Diam', 'number', required=True, default=0, unit='shared length',
                   description='Outer diameter.'),
    'HoleDiam': Field('HoleDiam', 'number', required=True, default=0, unit='shared length',
                       description='Drill diameter.'),
    'Group': Field('Group', 'integer', required=True, default=-1,
                    description='Managed pattern-group index; -1 means no group.'),
}, ('Enabled', 'Locked', 'X', 'Y', 'Diam', 'HoleDiam', 'Group'))

SLOT = Record('LibrarySlot', {
    'Index': Field('Index', 'integer', getter=lambda node: node._ordinal(),
                    ordinal_dependencies=lambda node: (node,),
                    description='Current zero-based library slot position.'),
    'LibPath': Field('LibPath', 'text', required=True, default='',
                      description='Library path associated with this slot.'),
    'VariablePath': Field('VariablePath', 'text', default=''),
    'Model3DFile_Variable': Field('Model3DFile_Variable', 'text', default='',
                                 description='Model path retained on a slot without a definition.'),
}, ('Index', 'LibPath'))

DEFINITION = Record('LibraryDefinition', {
    'Index': Field('Index', 'integer', getter=lambda node: node._ordinal(),
                    ordinal_dependencies=lambda node: (node,),
                    description='Current zero-based variant position within its library slot.'),
}, ('Index',))
