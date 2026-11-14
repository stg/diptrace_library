"""Text style belongs to symbol text, rather than every geometric drawing."""

TEXT_FIELDS = frozenset('''FontSize FontColor FontType FontName VectorFont FontWidth
FontScale FontMono TextAngle TextHorz TextVert TextAlign LineSpacing'''.split())


def normalize_text_style(shape):
    if shape['Type'] == 10:
        if (field := shape.child('PenWidth')) is not None:
            field.detach()
    else:
        for name in TEXT_FIELDS:
            if (field := shape.child(name)) is not None:
                field.detach()
        lines = shape.child('TextLine')
        if lines is not None:
            rows = lines.children('pt')
            if len(rows) == 1 and rows[0].values == ('',):
                rows[0].detach()


def supply_text_slots(shape, defaults):
    """Generate required wire slots on a detached serialization view."""
    normalize_text_style(shape)
    if shape.child('PenWidth') is None:
        shape.add('PenWidth', defaults['PenWidth'])
    for name in TEXT_FIELDS:
        if shape.child(name) is None:
            shape.add(name, defaults[name])
