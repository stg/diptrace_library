"""Build immutable family catalogues from authoritative record definitions."""
from collections.abc import Mapping
from types import MappingProxyType

from .schema import Record


def record_catalogue(*modules, overrides=(), roots=()):
    """Collect public records, checking names and owned-child type references.

    A family can explicitly select its completed definition over a shared base
    with the same name. Other conflicting names are errors. Optional roots
    restrict the result to records reachable through owned children and named
    tuple members that reuse a record's exact field definitions.
    """
    selected = {record.name: record for record in overrides}
    records = {}
    for module in modules:
        for name, value in vars(module).items():
            if name.startswith('_'):
                continue
            for record in value.values() if isinstance(value, Mapping) else (value,):
                if not isinstance(record, Record):
                    continue
                previous = records.get(record.name)
                if previous is not None and previous is not record and record.name not in selected:
                    raise ValueError(f'conflicting record definitions for {record.name}')
                records[record.name] = record
    for name, record in selected.items():
        if name not in records:
            raise ValueError(f'override has no declared record: {name}')
        records[name] = record
    tuples = {}
    for record in records.values():
        if record.parameters == tuple(record.fields):
            key = tuple(id(field) for field in record.fields.values())
            tuples.setdefault(key, []).append(record.name)
    pending = list(roots or records)
    reachable = {}
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        if name not in records:
            raise ValueError(f'undeclared child record: {name}')
        record = reachable[name] = records[name]
        pending.extend(name for child in record.children.values() for name in child.record.split('|'))
        for field in record.fields.values():
            if field.members:
                pending.extend(tuples.get(tuple(id(member) for member in field.members), ()))
    return MappingProxyType(dict(sorted(reachable.items())))
