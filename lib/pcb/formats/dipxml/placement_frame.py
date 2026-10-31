"""PCB placement geometry and XML's reusable footprint coordinate frame.

Placed physical data uses its actual side. XML's library definitions use the
top-side frame; placement side applies the reflection when they are installed.
Flip flags remain independent settings. Reflected views keep record identities
and ordering, so pad keys and drawing/dimension attachments need no remapping.
"""
from contextlib import contextmanager
from dataclasses import replace
from decimal import Decimal
from functools import wraps

from ....common.field_edits import preview_values
from ....common.geometry import reflected_angle


def _negate(value):
    return value.copy_negate() if isinstance(value, Decimal) else -value


def _field(record, name, operation=_negate):
    field = record.child(name)
    if field is not None:
        old, = field.arguments
        new = operation(old.value)
        if new != old.value:
            yield field, (replace(old, value=new, lexeme=None),)


def _points(collection):
    if collection is not None:
        for row in collection.children('pt'):
            x, y = row.arguments
            if x.value:
                yield row, (replace(x, value=_negate(x.value), lexeme=None), y)


def _pad(pad):
    yield from _field(pad, 'X')
    yield from _field(pad, 'PadShape_X')
    yield from _field(pad, 'PadAngle', reflected_angle)
    yield from _points(pad.child('PadPoints_New'))
    for terminal in pad.children('PadTerminal'):
        yield from _field(terminal, 'X')
        yield from _field(terminal, 'Angle', reflected_angle)
        yield from _points(terminal.child('ShapePoints'))
    for name in ('PadMask_TopSegments', 'PadMask_BotSegments'):
        for row in pad.select(name+'/pt'):
            x1, y1, x2, y2 = row.arguments
            # Each paste rectangle keeps its two Y edges and reflects its
            # horizontal interval. This also retains its row identity.
            values = (replace(x1, value=_negate(x2.value), lexeme=None), y1,
                      replace(x2, value=_negate(x1.value), lexeme=None), y2)
            if tuple(value.value for value in values) != row.values:
                yield row, values


def _geometry(pattern, *, raw=False):
    yield from _field(pattern, 'OriginX')
    pads = pattern.select('Pads/Pad')
    for pad in pads[1:-1] if raw else pads:
        yield from _pad(pad)
    for shape in pattern.select('Shapes/Shape'):
        if shape['Type'] <= 0:
            continue
        yield from _points(shape.child('Points_New'))
        if shape['Type'] == 7:
            yield from _field(shape, 'TextHorz')
            yield from _field(shape, 'TextAngle', reflected_angle)
    for hole in pattern.select('Holes/Hole'):
        if raw:
            # The shared XML constructor still has its serialized hole tuple;
            # normal assembly establishes the named placed-hole record later.
            if hole.values[0] and hole.values[2]:
                values = list(hole.arguments)
                values[2] = replace(values[2], value=_negate(values[2].value), lexeme=None)
                yield hole, tuple(values)
        elif hole['Enabled']:
            yield from _field(hole, 'X')
    for dimension in pattern.select('Dimensions/Dimension'):
        if dimension.get('Enabled', True):
            for name in ('X1', 'X2', 'XD'):
                yield from _field(dimension, name)


def install_geometry(component):
    """Modernize a newly read XML placement before model relationships bind."""
    if not component['BottomSide']:
        return
    changes = tuple(_geometry(component.one('Pattern'), raw=True))
    for field, values in changes:
        field.set_values(*values)


@contextmanager
def _xml_geometry(component):
    """Project top-side physical definitions without mutating source data.

    A field-value view retains the graph and all original identities. Both the
    physical library and pad placement options must read this same view.
    """
    changes = tuple(_geometry(component.one('Pattern'))) if component['BottomSide'] else ()
    with preview_values(changes):
        yield


def in_xml_frame(project):
    """Give physical-style and placement writers the same side conversion."""
    @wraps(project)
    def run(record, *args, **kwargs):
        component = record if record.kind == 'Component' else record.parent
        if component is None or component.kind != 'Component':
            return project(record, *args, **kwargs)
        # A style and its placement read the same conversion independently;
        # cached library definitions are already in their own library frame.
        with _xml_geometry(component):
            return project(record, *args, **kwargs)
    return run
