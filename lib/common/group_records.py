"""Local group data shared by symbol and footprint definitions."""
from .schema import Child, Field, Record


LOCAL_GROUP = Record('LocalGroup', {
    'Enabled': Field('Enabled', 'boolean', required=True, default=True),
    'Id': Field('Id', 'integer', required=True, default=0,
                description='Stored local group code, independent of collection position.'),
    **{name: Field(name, 'number', required=True, default=0, unit='shared length')
       for name in ('X', 'Y')},
}, parameters=('Enabled', 'Id', 'X', 'Y'))
LOCAL_GROUPS = Record('LocalGroups', {}, description='An ordered collection of LocalGroup records.',
    children={'pt': Child('pt', LOCAL_GROUP.name, maximum=None)})
