"""Strict current-model checks shared by PCB output adapters."""
from .errors import PcbError
from ...common.schema import MISSING


def field_value(node, name, *, destination='PCB'):
    """Read a current field or its schema default without modifying the model."""
    try:
        return node[name]
    except KeyError:
        default = node.schema.fields[name].default
        if default is MISSING:
            raise PcbError(f'{node.path}: {name} is needed for {destination} output') from None
        return default


def check(node, schema, *, destination):
    if node.schema is not schema:
        raise PcbError(f'{node.path}: expected {schema.name}')
    try:
        schema.validate_fields(node)
        schema.validate_children(node)
    except (TypeError, ValueError) as error:
        raise PcbError(str(error)) from error
    if len(node.arguments) != len(schema.parameters):
        raise PcbError(f'{node.path}: unexpected positional values')
    for child in node.children():
        field = schema.fields.get(child.kind)
        if field is not None and field.getter is not None:
            raise PcbError(f'{child.path}: calculated fields must not have stored copies')
        if field is None and child.kind not in schema.children:
            raise PcbError(f'{child.path}: no PCB {destination} projection')


def check_tree(node, schema, *, destination):
    """Validate a local owned definition, including its declared child domains."""
    check(node,schema,destination=destination)
    for child in node.children():
        if child.kind in schema.fields:
            continue
        expected = schema.children[child.kind].record
        if child.schema is None or child.schema.name != expected:
            raise PcbError(f'{child.path}: expected {expected}')
        check_tree(child,child.schema,destination=destination)
