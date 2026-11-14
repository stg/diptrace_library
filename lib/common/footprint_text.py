"""Keep text style and geometric strokes with their applicable drawing kinds.

Some serializations allocate text slots on lines and other geometric drawings.
Those inactive slots have no effect on the current drawing. Writers supply their
ordinary defaults on a detached view when the destination requires such slots.
Text uses FontWidth; its geometric Width slot is likewise inactive.
"""

TEXT_FIELDS = frozenset('''FontName VectorFont FontSize FontScale FontWidth FontMono
TextShow TextAngle TextHorz TextVert TextAlign LineSpacing'''.split())


def normalize_text_style(shape):
    if shape['Type'] == 7:
        if (width := shape.child('Width')) is not None:
            width.detach()
    else:
        for name in TEXT_FIELDS:
            if (field := shape.child(name)) is not None:
                field.detach()


def supply_text_slots(shape, defaults):
    """Generate serialization slots without adding them to the live model."""
    normalize_text_style(shape)
    if shape.child('Width') is None:
        shape.add('Width', defaults['Width'])
    for name in TEXT_FIELDS:
        if shape.child(name) is None:
            shape.add(name, defaults[name])
