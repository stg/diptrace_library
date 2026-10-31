"""Identity-based membership in a cached symbol's or footprint's local groups."""
from dataclasses import replace

from ...common.group_records import LOCAL_GROUP
from ...common.references import ReferenceError
from ...common.schema import Child, Field, Record
from .relationships import optional_reference_fields


PATTERN_GROUP = 'pattern-group'
SYMBOL_GROUP = 'symbol-group'
ROLES = (PATTERN_GROUP, SYMBOL_GROUP)

GROUP = replace(LOCAL_GROUP, name='PcbLocalGroup', fields={**LOCAL_GROUP.fields,
    'Id': Field('Id', 'integer', getter=lambda group: group._ordinal(),
        ordinal_dependencies=lambda group: (group,), description='Calculated local group position.')})
GROUPS = Record('PcbLocalGroups', {}, children={'pt': Child('pt', GROUP.name, maximum=None)})


def grouped(schema, role, *, name):
    """Keep physical fields shared while giving PCB its named identity access."""
    return replace(schema, name=name, fields={**schema.fields,
        **optional_reference_fields('Group', 'GroupId', role)},
        parameters=tuple(field for field in schema.parameters if field != 'Group'))


def issue_role(issue):
    return next((role for role in ROLES if issue.message.startswith(role+':')), None)


def issue_fields(issue):
    if issue_role(issue) is None:
        return ()
    source = issue.source
    return ((source, source.schema.fields['Group']),)


def validate_issue(document, issue):
    role = issue_role(issue)
    if role is None:
        return
    context = owner(issue.source)
    collection = 'Pattern_Groups' if role == PATTERN_GROUP else 'Groups'
    scope = context.child(collection) if context is not None else None
    if (scope is None or issue.collections != (scope,)
            or issue.source.child('UnresolvedGroupId') is None):
        raise ReferenceError('resolve or clear the unavailable local group before changing its scope')


def owner(source):
    parent = source.parent
    return parent.parent if parent is not None else None


def validate_reference(document, reference, target):
    if reference.role not in ROLES:
        return
    source = reference.source
    context = owner(source)
    collection = 'Pattern_Groups' if reference.role == PATTERN_GROUP else 'Groups'
    kind = 'Pattern' if reference.role == PATTERN_GROUP else 'Part'
    field = source.schema.fields.get('Group') if source.schema is not None else None
    if (field is None or field.kind != 'reference' or context is None or context.kind != kind
            or target.schema is not GROUP or target.parent is not context.child(collection)
            or target._owner() is not document or not target['Enabled']):
        raise ReferenceError('local group must belong to the same symbol or footprint')
    if any(link.uid != reference.uid for link in document.references.outgoing(source, role=reference.role)):
        raise ReferenceError('object already has a local group')


def validate_references(document, references):
    for reference in references:
        validate_reference(document, reference, reference.target)
