"""Shared public ASC footprint shorthand, expanded into owned named records.

Document adapters choose their terminal container and model-placement tuple.
The helpers consume syntax-only counts and superseded drawing header values.
"""


MODEL_FIELDS = ('Mirror', 'NoSearch', 'Units', 'IPC_XOff', 'IPC_YOff',
                'AutoHeight', 'AutoColor', 'Type', 'KeepPins')


def unpack_terminals(parent, *, container='PadTerminalCount', counted=True):
    collection = parent.one(container)
    terminals = collection.children('PadTerminal')
    if collection.values != ((len(terminals),) if counted else ()):
        raise ValueError(f'{collection.path}: terminal count does not match records')
    if len(collection.children()) != len(terminals):
        raise ValueError(f'{collection.path}: unexpected terminal records')
    for index, terminal in enumerate(terminals):
        terminal.set_values(index)
        terminal.move_to(parent)
    if not counted:
        collection.detach()


def unpack_model(model, *, fields=MODEL_FIELDS):
    values = model.one('pt').arguments
    if len(values) != 9+len(fields):
        raise ValueError(f'{model.path}: expected {9+len(fields)} model placement values')
    model.one('pt').detach()
    for index, name in enumerate(('Rotate', 'Offset', 'Zoom')):
        vector = model.add(name)
        for axis, value in zip(('X', 'Y', 'Z'), values[index*3:index*3+3]):
            vector.add(axis, value)
    for name, value in zip(fields, values[9:]):
        model.add(name, value)


def unpack_pattern_shapes(container, *, pad_id=True, points_name='Points_New', header_fields=()):
    records, current = [], None
    for record in list(container.children()):
        if record.kind == 'Shape':
            if len(record.arguments) != 18:
                raise ValueError(f'{record.path}: expected 18 footprint drawing values')
            current = record
            records.append((record, []))
        elif current is None:
            raise ValueError(f'{record.path}: footprint field precedes its Shape')
        else:
            records[-1][1].append(record)
    for index, (shape, siblings) in enumerate(records):
        header = shape.arguments
        shape.set_values(index)
        for name, value in (('Type', header[0]), ('Locked', header[1]),
                ('FontName', header[10]), ('VectorFont', header[11]),
                ('FontSize', header[12]), ('FontScale', header[13]),
                ('FontWidth', header[14]), ('TextShow', header[17])):
            shape.add(name, value)
        for sibling in siblings:
            sibling.move_to(shape)
        for name, position in header_fields:
            if shape.child(name) is None:
                shape.add(name, header[position])
        # Named/current fields supersede the old header occurrences.
        if shape.child('Width') is None:
            shape.add('Width', header[16])
        if points_name != 'Points_New' and (points := shape.child(points_name)) is not None:
            if shape.child('Points_New') is not None:
                raise ValueError(f'{shape.path}: duplicate current drawing points')
            points.kind = 'Points_New'
        if (points := shape.child('Points')) is not None:
            points.detach()
        if shape.child('Points_New') is None:
            shape.add('Points_New')
        if shape.child('TextLine') is None:
            shape.add('TextLine').add('pt', header[9])
        if pad_id:
            shape.add('PadId', -1).annotations['asc_omit'] = 'not present in ASC'
