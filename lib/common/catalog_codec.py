"""Shared classification rows and suggested names in design-file records."""


def read_category_types(reader, owner, kind):
    count = reader.count(kind)
    types = owner.add(kind, count)
    for _ in range(count):
        reader.record(types, 'CategoryType', 'text', 'text', 'integer', 'integer')
    return types


def read_possible_names(reader, owner):
    count = reader.count('possible footprint names')
    names = owner.add('PossibleNames', count)
    for _ in range(count):
        reader.record(names, 'PossibleName', 'text')
    return names


def write_category_types(writer, owner, kind):
    writer.rows(owner.child(kind), 'CategoryType', 'text text integer integer')
