"""Small shared views for owned cached symbols and footprints."""
from ....common.model import Element
from ....common import library_metadata, user_fields
from ...model import local_groups
from .projection import collection, flag


def prefix(output, *, keep=()):
    """Prefix a detached output tree; callers never pass authored source nodes."""
    if output.kind in keep:
        return output
    output.kind = 'cl_'+output.kind
    for child in output.children():
        prefix(child, keep=keep)
    return output


def groups(owner, name):
    output = Element(name)
    for group in collection(owner, name, local_groups.GROUPS, local_groups.GROUP):
        output.add('Pattern_Group' if name == 'Pattern_Groups' else 'Group',
                   flag(group['Enabled']), group['Id'], group['X'], group['Y'])
    return output


def user_field_rows(owner, *, symbol=False):
    schema = user_fields.COMPONENT_USER_FIELDS if symbol else user_fields.USER_FIELDS
    record = user_fields.COMPONENT_USER_FIELD if symbol else user_fields.USER_FIELD
    output = Element('UserFields')
    for row in collection(owner, 'UserFields', schema, record):
        output.add('UserField', *(row[name] for name in record.parameters))
    return output


def classifications(owner, family):
    members = collection(owner, family+'_CategoryTypes', library_metadata.CLASSIFICATIONS,
                         library_metadata.CATEGORY_TYPE)
    output = Element('CategoryTypes', len(members))
    for row in members:
        output.add('CategoryType', *row.arguments)
    return output
