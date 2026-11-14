"""Standalone entry names, organization, fields and model placement."""
from ....common.catalog_codec import read_category_types, read_possible_names
from ....common.drawing_codec import read_groups
from ....common.library_codec import discard_legacy_groups
from ....common.library_model import read_library_model
from .parameters import _fields


def read_metadata(reader, pattern):
    version = reader.header.version
    _fields(reader, pattern, 'text', 'Name RefDes Value')
    _fields(reader, pattern, 'number', 'OriginX OriginY')
    if version >= 20:
        _fields(reader, pattern, 'boolean', 'OriginCross OriginCircle')
        _fields(reader, pattern, 'integer', 'OriginCommon OriginCourtyard')
        _fields(reader, pattern, 'text', 'Name_Description Name_Unique RecoveryCode')
        _fields(reader, pattern, 'boolean', 'RecoveryCode_Generator RecoveryCode_Model')
        reader.field_into(pattern, 'Pattern_Manufacturer', 'text')
        read_groups(reader, pattern, 'Pattern_Groups')
    else:
        discard_legacy_groups(reader, ('Pads', 'Shapes', 'Holes', 'Dimensions'))
    fields = reader.add(pattern, 'UserFields')
    for _ in range(reader.count('pattern user fields')):
        reader.record(fields, 'UserField', 'text', 'text', 'integer')
    read_library_model(reader, pattern, variable_filename=version >= 24,
                       authoring_properties=version >= 20, keep_pins=version >= 22)
    if version >= 18:
        reader.field_into(pattern, 'Mounting', 'integer')
        _fields(reader, pattern, 'text', 'Datasheet Pattern_CategoryName')
        reader.field_into(pattern, 'Pattern_CategoryIndex', 'integer')
        read_category_types(reader, pattern, 'Pattern_CategoryTypes')
        read_possible_names(reader, pattern)
    else:
        modes = {pad['SurfacePad'] for index,pad in enumerate(pattern.select('Pads/Pad'))
                 if index > 0 and pad['Number_New'] == index}
        mounting = {frozenset(): -1, frozenset((False,)): 0,
                    frozenset((True,)): 1, frozenset((False, True)): 3}[frozenset(modes)]
        reader.add_into(pattern, 'Mounting', mounting)
        reader.add_into(pattern, 'Datasheet', '')
    flags = [reader.boolean() for _ in range(reader.count('verification flags'))]
    reader.add_into(pattern, 'Verification', *(flags+[False]*4)[:4])
    if version >= 23:
        suppliers = reader.add(pattern, 'Suppliers')
        _fields(reader, suppliers, 'text', 'PartNumber Manufacturer Pattern Supplier Currency')
    return pattern
