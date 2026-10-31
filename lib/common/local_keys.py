"""Consume public local keys without inventing a missing target."""
from .schema import Child, Field, Record


UNRESOLVED_KEY = Record('UnresolvedKey', {
    'Field': Field('Field', 'text', required=True, default='', description='Name of the unresolved relationship field.'),
    'Id': Field('Id', 'integer', required=True, default=0, description='Unresolved public target key.'),
}, parameters=('Field', 'Id'))
UNRESOLVED_KEYS = Record('UnresolvedKeys', {}, description='An ordered collection of UnresolvedKey records.',
                         children={'Key': Child('Key', UNRESOLVED_KEY.name, maximum=None)})


def definition(node):
    parent = node.parent
    if parent is None:
        return None
    if node.kind == 'UnresolvedKeys' and parent.schema is not None:
        child = parent.schema.children.get(node.kind)
        if child is not None and child.record == UNRESOLVED_KEYS.name:
            return UNRESOLVED_KEYS
    if node.kind == 'Key' and parent.schema is UNRESOLVED_KEYS:
        return UNRESOLVED_KEY
    return None


def map_key(owner, name, key, mapping):
    if key < 0 or key in mapping:
        return mapping.get(key, key)
    keys = owner.child('UnresolvedKeys') or owner.add('UnresolvedKeys')
    keys.add('Key', name, key)
    return -1
