"""Named component marking placements, independent of text-layout algorithms."""
from dataclasses import replace

from ...common.schema import Child, Field, Record
from ...common.user_fields import USER_FIELD as BASE_USER_FIELD


NAMES = ('RefDes', 'Name', 'Value', 'Pattern', 'Manufacturer', 'Datasheet')
SIDES = ('Silk', 'Assy')


def fields(prefix):
    """One marking's selection, alignment and authored placement properties."""
    return {
        **{prefix+name: Field(prefix+name, 'integer', default=0)
           for name in ('Show', 'Align', 'Horz', 'Vert')},
        **{prefix+axis: Field(prefix+axis, 'number', default=0, unit='shared length')
           for axis in ('X', 'Y')},
        prefix+'Angle': Field(prefix+'Angle', 'number', default=0, unit='radians'),
    }


COMPONENT_FIELDS = {name: field for label in NAMES for side in SIDES
                    for name, field in fields(label+'_'+side).items()}
GLOBAL_FIELDS = {label+'_Global_'+side+name: Field(label+'_Global_'+side+name, 'integer')
                 for label in NAMES for side in SIDES for name in ('Show', 'Align')}


def field_key(name):
    """Match custom marking categories without literal spaces or letter case."""
    return name.replace(' ', '').lower()


GLOBAL_USER_FIELD = Record('PcbGlobalUserField', {
    'Name': Field('Name', 'text', required=True, default=''),
    'Value': Field('Value', 'text', getter=lambda node: field_key(node['Name']),
        value_dependencies=lambda node: ((node, 'Name'),),
        description='Generated case-insensitive field-name key used by ASC and DIP.'),
    **{side+name: Field(side+name, 'integer') for side in SIDES for name in ('Show', 'Align')},
})
GLOBAL_USER_FIELDS = Record('PcbGlobalUserFields', {}, children={
    'UserField': Child('UserField', GLOBAL_USER_FIELD.name, maximum=None)})


def global_definition(node):
    parent = node.parent
    if parent is not None and parent.kind == 'Board' and node.kind == 'Userfields_Global':
        return GLOBAL_USER_FIELDS
    if (parent is not None and parent.kind == 'Userfields_Global' and
            parent.parent is not None and parent.parent.kind == 'Board' and node.kind == 'UserField'):
        return GLOBAL_USER_FIELD
    return None

USER_FIELD = replace(BASE_USER_FIELD, name='PcbUserField', fields={
    **BASE_USER_FIELD.fields, **fields('Silk'), **fields('Assy')})
USER_FIELDS = Record('PcbUserFields', {}, children={
    'UserField': Child('UserField', USER_FIELD.name, maximum=None)})

# Public drawing text selections. User fields follow their current ordering.
TEXT_FIELDS = {1: 'Name', 2: 'RefDes', 3: 'Value', 6: 'Datasheet', 7: 'Manufacturer'}
PATTERN_TEXT_FIELDS = {4: 'Name', 5: 'Name_Unique'}
USER_FIELD_OFFSET = 20
