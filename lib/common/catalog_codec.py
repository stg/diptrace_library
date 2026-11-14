"""Shared classification rows and suggested names in design-file records."""


def read_categories(reader, owner, name='Categories'):
    """Read a catalogue with declared keys and nested types/subtypes."""
    categories = reader.add(owner, name)
    for _ in range(reader.count('library categories')):
        category = reader.record(categories, 'Category', 'text', 'integer')
        for _ in range(reader.count('category types')):
            kind = reader.record(category, 'Type', 'text', 'integer')
            for _ in range(reader.count('category subtypes')):
                reader.record(kind, 'Subtype', 'text', 'integer')
    return categories


def read_category_types(reader, owner, kind):
    count = reader.count(kind)
    types = reader.add(owner, kind, count)
    for _ in range(count):
        reader.record(types, 'CategoryType', 'text', 'text', 'integer', 'integer')
    return types


def read_possible_names(reader, owner):
    count = reader.count('possible footprint names')
    names = reader.add(owner, 'PossibleNames', count)
    for _ in range(count):
        reader.record(names, 'PossibleName', 'text')
    return names


def write_category_types(writer, owner, kind):
    writer.rows(owner.child(kind), 'CategoryType', 'text text integer integer')


def write_categories(writer, owner, name='Categories'):
    """Generate catalogue counts from named records and their declared keys."""
    categories=owner.one(name).children('Category')
    writer.integer(len(categories))
    for category in categories:
        writer.fields(category,'text','Name')
        writer.field(category,'Index','integer')
        types=category.children('Type')
        writer.integer(len(types))
        for kind in types:
            writer.field(kind,'Name','text')
            writer.field(kind,'Index','integer')
            subtypes=kind.children('Subtype')
            writer.integer(len(subtypes))
            for subtype in subtypes:
                writer.field(subtype,'Name','text')
                writer.field(subtype,'Index','integer')
