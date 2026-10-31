"""Declared scalar conversions for PCB ASC, preserving authored strings."""
from ....common.model import Value
from ..errors import PcbError


def rename(owner, names):
    changes = []
    for name, target in names.items():
        rows = owner.children(name)
        if len(rows) > 1:
            raise PcbError(f'{owner.path}: ambiguous {name}/{target} fields')
        if rows:
            changes.append((rows[0], target))
    moving = {row for row, _ in changes}
    targets = [target for _, target in changes]
    if (len(set(targets)) != len(targets) or
            any(row not in moving for target in targets for row in owner.children(target))):
        raise PcbError(f'{owner.path}: ambiguous field names')
    for row, target in changes:
        row.kind = target


def boolean(value, path):
    if value.kind == 'boolean':
        return value
    if value.value not in ('Y', 'N'):
        raise PcbError(f'{path}: expected boolean Y or N')
    return Value(value.value == 'Y', 'boolean', source=value.source)


def booleans(owner, names):
    for name in names:
        field = owner.child(name)
        if field is not None:
            if len(field.arguments) != 1 or field.children():
                raise PcbError(f'{field.path}: expected one boolean')
            field.set_values(boolean(field.arguments[0], field.path))


def move_fields(owner, target, names):
    """Move named scalar declarations after checking all destination names."""
    changes, destinations = [], set()
    for source, name in names.items():
        rows = owner.children(source)
        if len(rows) > 1 or rows and (target.child(name) is not None or name in destinations):
            raise PcbError(f'{target.path}: ambiguous {name} setting')
        if rows:
            changes.append((rows[0], name))
            destinations.add(name)
    for row, name in changes:
        row.kind = name
        row.move_to(target)


def numeric_row(row, count, *, kind='pt', flags=(), integers=()):
    """Validate a compact geometry row, converting only declared flag columns."""
    if row.kind != kind or len(row.arguments) != count or row.children():
        raise PcbError(f'{row.path}: expected {count} {kind} values')
    values = list(row.arguments)
    for position in flags:
        values[position] = boolean(values[position], row.path)
    for position, value in enumerate(values):
        if position in flags:
            continue
        if (value.kind != 'number' or value.unit or
                position in integers and type(value.value) is not int):
            raise PcbError(f'{row.path}: invalid numeric value at column {position+1}')
    return values


def counted_rows(container):
    rows = container.children()
    if (len(container.values) != 1 or type(container.values[0]) is not int
            or container.values[0] != len(rows)):
        raise PcbError(f'{container.path}: count does not match rows')
    container.set_values()
    return rows
