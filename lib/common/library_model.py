"""Library-footprint 3D attachment records, with caller-owned revision gates."""
from .footprint_codec import read_model_extensions, write_model_extensions


def read_library_model(reader, pattern, *, variable_filename,
                       authoring_properties, keep_pins):
    model = reader.add(pattern, 'Model3D')
    # Older library filenames use the long ANSI length independently of names.
    length_mode = reader.ansi_length_bytes
    try:
        reader.ansi_length_bytes = 3
        reader.field_into(model, 'Model3DFile', 'text')
    finally:
        reader.ansi_length_bytes = length_mode
    for name in ('Offset', 'Rotate', 'Zoom'):
        vector = reader.add(model, name)
        reader.fields(vector, ((axis, 'number') for axis in ('X', 'Y', 'Z')))
    reader.field_into(model, 'Mirror', 'boolean')
    if variable_filename:
        reader.field_into(model, 'Model3DFile_Variable', 'text')
    else:
        reader.add_into(model, 'Model3DFile_Variable', model['Model3DFile'])
    reader.field_into(model, 'NoSearch', 'boolean')
    reader.field_into(model, 'Units', 'integer')
    if authoring_properties:
        read_model_extensions(reader, pattern)
    if keep_pins:
        reader.field_into(model, 'KeepPins', 'boolean')
    return model


def write_library_model(writer, pattern, *, variable_filename,
                        authoring_properties, keep_pins):
    model = pattern.one('Model3D')
    writer.field(model, 'Model3DFile', 'text')
    for name in ('Offset', 'Rotate', 'Zoom'):
        writer.fields(model.one(name), 'number', 'X Y Z')
    writer.field(model, 'Mirror', 'boolean')
    if variable_filename:
        writer.field(model, 'Model3DFile_Variable', 'text')
    writer.field(model, 'NoSearch', 'boolean')
    writer.field(model, 'Units', 'integer')
    if authoring_properties:
        write_model_extensions(writer, pattern)
    if keep_pins:
        writer.field(model, 'KeepPins', 'boolean')
