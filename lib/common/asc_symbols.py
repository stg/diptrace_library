"""Current symbol geometry and text from public ASC drawing records."""


def unpack_symbol_shape(shape):
    """Keep current text and physical points; discard superseded point views."""
    for name in ('Points',):
        field = shape.child(name)
        if field is not None:
            field.detach()
    if shape.child('Points_New') is None:
        shape.add('Points_New')
    if (lines := shape.child('TextLines')) is not None:
        if shape.child('TextLine') is not None or lines.values:
            raise ValueError(f'{shape.path}: duplicate or invalid current text lines')
        for row in lines.children():
            if row.kind != 'pt' or len(row.values) != 1 or row.children() or not isinstance(row.values[0], str):
                raise ValueError(f'{row.path}: expected one text line')
        lines.kind = 'TextLine'
    if shape.child('TextLine') is None:
        lines = shape.add('TextLine')
        if shape.scalar('Name', ''):
            lines.add('pt', shape.scalar('Name'))
