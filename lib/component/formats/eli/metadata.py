"""Standalone attachment organization following its physical arrays."""
from ....common.catalog_codec import read_category_types, read_possible_names
from ....common.drawing_codec import read_groups
from ....common.library_codec import discard_legacy_groups
from ....common.library_model import read_library_model


def read_physical_metadata(reader, pattern):
    version = reader.header.version
    if version >= 27:
        read_groups(reader, pattern, 'Pattern_Groups')
    else:
        discard_legacy_groups(reader, ('Pads', 'Shapes', 'Holes'))
    fields = reader.add(pattern, 'UserFields')
    for _ in range(reader.count('footprint user fields')):
        reader.record(fields, 'UserField', 'text', 'text', 'integer')
    read_library_model(reader, pattern, variable_filename=version >= 31,
                       authoring_properties=version >= 27, keep_pins=version >= 29)
    if version >= 24:
        reader.field_into(pattern, 'Mounting', 'integer')
        reader.field_into(pattern, 'Pattern_CategoryName', 'text')
        reader.field_into(pattern, 'Pattern_CategoryIndex', 'integer')
        read_category_types(reader, pattern, 'Pattern_CategoryTypes')
        read_possible_names(reader, pattern)
    return pattern


def _long_text(reader, owner, name):
    """Long library strings predate the ordinary Unicode name encoding."""
    length_mode = reader.ansi_length_bytes
    try:
        reader.ansi_length_bytes = 3
        reader.field_into(owner, name, 'text')
    finally:
        reader.ansi_length_bytes = length_mode


def read_symbol_metadata(reader, part):
    version = reader.header.version
    if version >= 27:
        read_groups(reader, part, 'Groups')
    else:
        discard_legacy_groups(reader, ('Pins', 'Shapes'))
    fields = reader.add(part, 'UserFields')
    for _ in range(reader.count('symbol user fields')):
        reader.record(fields, 'UserField', 'text', 'text', 'integer')
    reader.field_into(part, 'ModelType', 'integer')
    _long_text(reader, part, 'ModelString')
    body = reader.add(part, 'ModelBody')
    for _ in range(reader.count('simulation model lines')):
        _long_text(reader, reader.add(body, 'Line'), 'Text')
    reader.field_into(part, 'SubfolderIndex', 'integer')
    flags = [reader.boolean() for _ in range(reader.count('verification flags'))]
    reader.add_into(part, 'Verification', *(flags+[False]*7)[:7])
    _long_text(reader, part, 'Datasheet')
    if version >= 24:
        reader.field_into(part, 'Manufacturer', 'text')
        reader.field_into(part, 'Component_CategoryName', 'text')
        reader.field_into(part, 'Component_CategoryIndex', 'integer')
        read_category_types(reader, part, 'Component_CategoryTypes')
    if version >= 30:
        supplier = reader.add(part, 'Suppliers')
        reader.fields(supplier, ((name, 'text') for name in
            ('PartNumber', 'Manufacturer', 'Pattern', 'Supplier', 'Currency')))
    return part
