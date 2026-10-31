"""Small, strict building blocks for detached PCB ASC output sections."""
from ....common.schema import MISSING
from ..errors import PcbError
from ..output_validation import check as _check, field_value
from ..output_indices import non_signal_number as _non_signal_number


def check(node, schema):
    return _check(node,schema,destination='ASC')


def value(node, name):
    """Read a current field, using its declared default only when it is absent."""
    return field_value(node, name, destination='ASC')


def flag(value):
    return 'Y' if value else 'N'


def non_signal_number(node, *, report=None):
    """Keep absent and unresolved remembered custom-layer choices distinct."""
    return _non_signal_number(node, destination='asc', report=report)


def fields(node, output, *, exclude=(), names=None):
    """Write stored scalar fields; references and adapter indices stay explicit."""
    names = names or {}
    for name, field in node.schema.fields.items():
        if field.getter is not None or name in exclude:
            continue
        if node.child(name) is None and field.default is MISSING:
            continue
        current = value(node, name)
        output.add(names.get(name, name), flag(current) if field.kind == 'boolean' else current)


def rows(collection, schema, record):
    check(collection, schema)
    result = tuple(collection.children())
    for row in result:
        check(row, record)
    return result


def collection(node, name, schema, record):
    """Return validated optional collection members without manufacturing data."""
    source = node.child(name)
    return () if source is None else rows(source, schema, record)


def layer_rows(owner, name, schema, record, layers, *, uniform=False):
    """Put identity-scoped rows in their destination stack order."""
    from ..output_indices import ordered_layer_rows
    members = collection(owner, name, schema, record)
    return ordered_layer_rows(members, layers, uniform=uniform, path=owner.path+'/'+name)
