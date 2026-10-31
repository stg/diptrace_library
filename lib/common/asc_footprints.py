"""Shared public ASC footprint shorthand, expanded into owned named records.

Document adapters choose their terminal container and model-placement tuple.
The helpers consume syntax-only counts and superseded drawing header values.
"""
from .model import Element


MODEL_FIELDS = ('Mirror', 'NoSearch', 'Units', 'IPC_XOff', 'IPC_YOff',
                'AutoHeight', 'AutoColor', 'Type', 'KeepPins')


def model3d_arguments(model, *, fields=MODEL_FIELDS):
    """Read a dialect's placement tuple from the same named physical data."""
    flat = model.child('pt') or model.child('cl_pt')
    if flat is not None:
        return flat.arguments
    values = []
    for name in ('Rotate', 'Offset', 'Zoom'):
        vector = model.child(name)
        if vector is None:
            raise ValueError(f'{model.path}: missing {name}')
        values.extend(vector.child(axis) for axis in ('X', 'Y', 'Z'))
    values.extend(model.child(name) for name in fields)
    if any(item is None or len(item.arguments) != 1 or item.children() for item in values):
        raise ValueError(f'{model.path}: incomplete 3D placement data')
    return tuple(item.arguments[0] for item in values)


def project_terminals(parent, *, container='PadTerminalCount', counted=True,
                      points_counted=True, convert=lambda value: value):
    """Project physical terminals, with counts chosen by the document dialect."""
    terminals = parent.children('PadTerminal')
    output = Element(container, *((len(terminals),) if counted else ()))
    names = ('Type', 'X', 'Y', 'Angle', 'ShapeWidth', 'ShapeHeight', 'ShapeCorner')
    for terminal in terminals:
        if any(child.kind not in (*names, 'ShapePoints', 'Index') for child in terminal.children()):
            raise ValueError(f'{terminal.path}: unknown terminal data')
        row = output.add('PadTerminal')
        for name in names:
            field = terminal.one(name)
            if len(field.arguments) != 1 or field.children():
                raise ValueError(f'{field.path}: expected one terminal value')
            row.add(name, convert(field.arguments[0]))
        points = terminal.child('ShapePoints')
        vertices = points.children() if points is not None else ()
        target = row.add('ShapePoints', *((len(vertices),) if points_counted else ()))
        for point in vertices:
            if point.kind != 'pt' or len(point.arguments) != 2 or any(
                    child.kind not in ('X', 'Y') for child in point.children()):
                raise ValueError(f'{point.path}: expected terminal XY point')
            target.add('pt', *(convert(argument) for argument in point.arguments))
    return output


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


def _detach_flat_fields(container, records):
    """Partition an unbound syntax stream once, retaining every node identity.

    Normal parsing has no schemas or reference relationships yet. Repeated moves
    from its large flat list would keep rebuilding and scanning that same list.
    Bound trees retain the ordinary coordinated move path.
    """
    owner = container._owner()
    if (container.schema is not None or owner is not None and len(owner.references)
            or any(shape.schema is not None or any(field.schema is not None for field in fields)
                   for shape, fields in records)):
        return False
    fields = {field for _, siblings in records for field in siblings}
    if fields:
        container._items = [item for item in container._items
                            if not isinstance(item, Element) or item not in fields]
        for field in fields:
            field._parent = None
        container._touch(reordered=True)
    return True


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
    detached = _detach_flat_fields(container, records)
    for index, (shape, siblings) in enumerate(records):
        header = shape.arguments
        shape.set_values(index)
        for name, value in (('Type', header[0]), ('Locked', header[1]),
                ('FontName', header[10]), ('VectorFont', header[11]),
                ('FontSize', header[12]), ('FontScale', header[13]),
                ('FontWidth', header[14]), ('TextShow', header[17])):
            shape.add(name, value)
        for sibling in siblings:
            if detached:
                shape.append(sibling)
            else:
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
        if (lines := shape.child('TextLines')) is not None:
            if shape.child('TextLine') is not None or lines.values:
                raise ValueError(f'{shape.path}: duplicate or invalid current drawing text')
            for line in lines.children():
                if (line.kind != 'TextLine' or len(line.values) != 1 or line.children()
                        or not isinstance(line.values[0], str)):
                    raise ValueError(f'{line.path}: expected one text line')
                line.kind = 'pt'
            lines.kind = 'TextLine'
        if shape.child('TextLine') is None:
            shape.add('TextLine').add('pt', header[9])
        if pad_id:
            shape.add('PadId', -1).annotations['asc_omit'] = 'not present in ASC'
