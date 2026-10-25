"""Named user text/link data shared by document families."""
from .schema import Child, Field, Record
from .label_records import MARKING


USER_FIELD = Record('UserField', {
    'Name': Field('Name', 'text', required=True, default='', description='User-visible field name.'),
    'Value': Field('Value', 'text', required=True, default='', description='Field text or link.'),
    'Type': Field('Type', 'integer', required=True, default=0, description='0 Text, 1 Link.'),
}, parameters=('Name', 'Value', 'Type'))

COMPONENT_USER_FIELD = Record('ComponentUserField', {
    **USER_FIELD.fields, **MARKING.fields,
}, parameters=(*USER_FIELD.parameters, *MARKING.parameters),
    description='Component user text/link and its label display and placement.')

USER_FIELDS = Record('UserFields', {},
    description='An ordered collection of UserField records.',
    children={'UserField': Child('UserField', USER_FIELD.name, maximum=None)})
COMPONENT_USER_FIELDS = Record('ComponentUserFields', {},
    description='An ordered collection of ComponentUserField records.',
    children={'UserField': Child('UserField', COMPONENT_USER_FIELD.name, maximum=None)})
