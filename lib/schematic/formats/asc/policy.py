"""ASC scalar projection, separate from stored document values.

The generic ASC editor preserves source spelling. Conversion from DCH instead
needs the format export rules: four-place binary floating-point rounding and
the quoted-text sanitizer. Applying these rules never mutates the document.
"""
from decimal import Decimal
import math





def number_text(value: int | float | Decimal) -> str:
    """Number text."""
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("ASC numbers must be finite")
    scaled = round(number * 10_000)
    whole, fraction = divmod(abs(scaled), 10_000)
    rendered = str(whole)
    if fraction:
        rendered += '.' + f'{fraction:04d}'.rstrip('0')
    return ('-' if scaled < 0 else '') + rendered


def quoted_text(value: str) -> str:
    """Quoted text."""
    return '"' + value.replace('"', '!').replace('\r', '!').replace('\n', '!') + '"'


def _redundant_cell_text(node):
    if node.kind != 'Text' or node.parent is None or node.parent.kind != 'Cell' or len(node.arguments) != 1:
        return False
    lines = node.parent.child('TextLine')
    if lines is None:
        return False
    rows = lines.children()
    return (all(row.kind == 'pt' and len(row.arguments) == 1 and row.arguments[0].kind == 'string'
                and not row.children() for row in rows) and
            node.values[0] == '\n'.join(row.values[0] for row in rows))


def _receiver_normalized_text(node, index):
    """Known ASC receiver fields that interpret literal ! as a space.

    This is a reader compatibility diagnostic, not a rewrite of the file or
    the shared model. Other strings have independent reader rules.
    """
    def placed(part):
        return (part is not None and part.kind == 'Part' and part.parent is not None
                and part.parent.kind == 'Components' and part.parent.parent is not None
                and part.parent.parent.kind == 'Schematic')

    if node.kind == 'Part' and index < 2:
        return placed(node)
    if node.kind in ('Value', 'Manufacturer', 'PartName', 'ModelString', 'ModelBody'):
        return placed(node.parent)
    if node.kind == 'UserField' and index < 2:
        return node.parent is not None and node.parent.kind == 'UserFields' and placed(node.parent.parent)
    if node.kind == 'pt' and node.parent is not None and node.parent.kind == 'TextLine':
        shape = node.parent.parent
        return (shape is not None and shape.kind == 'Shape' and shape.scalar('Type') == 10
                and shape.parent is not None and shape.parent.kind == 'Shapes'
                and shape.parent.parent is not None and shape.parent.parent.kind == 'Schematic')
    return False


def project_text(document, *, encoding='cp1252', report=None):
    """Apply ASC text restrictions to an owned output view, after layout.

    Intermediate record projections retain literal text. This single boundary
    makes restrictions observable without guessing which source fields export.
    """
    from ....common.conversion import (info, warn)
    from ....common.model import (Value)
    from ....common.text.windows_1252 import (project as ansi_text)
    import codecs
    encoding = codecs.lookup(encoding).name
    sanitized, encoded, compatibility, receiver_text = [], [], [], []
    for node in document.root.walk():
        redundant = _redundant_cell_text(node)
        sanitize_changed = encode_changed = receiver_changed = False
        for index, value in enumerate(node.arguments):
            if value.kind != 'string':
                continue
            receiver_changed |= '!' in value.value and _receiver_normalized_text(node, index)
            text = quoted_text(value.value)[1:-1]
            projected = ansi_text(text) if encoding == 'cp1252' else text.encode(encoding).decode(encoding)
            sanitize_changed |= text != value.value
            encode_changed |= projected != text
            if projected != value.value:
                node.set_argument(index, Value(projected, value.kind, value.unit, source=value.source))
        if redundant and (sanitize_changed or encode_changed):
            compatibility.append(node)
        elif sanitize_changed:
            sanitized.append(node)
        if encode_changed and not redundant:
            encoded.append(node)
        if receiver_changed and not redundant:
            receiver_text.append(node)
    if compatibility:
        info(report, 'asc-cell-text-compatibility', 'asc', 'the redundant legacy cell text representation is normalized', compatibility,
             recoverability='TextLine supplies the current cell text; restrictions of those line values are reported separately')
    if sanitized:
        warn(report, 'asc-text-sanitization', 'asc', 'quotes and line breaks in ASC strings become exclamation marks', sanitized,
             recoverability='original characters cannot be recovered from ASC; authoring text remains intact')
    if encoded:
        warn(report, 'asc-text-encoding', 'asc', f'ASC strings use {encoding} character substitutions', encoded,
             recoverability='original characters cannot be recovered from ASC; authoring Unicode remains intact')
    if receiver_text:
        warn(report, 'asc-reader-text-normalization', 'asc',
             'the receiving application replaces literal ! with spaces in these text fields', receiver_text,
             recoverability='literal ! remains in the ASC file and this library preserves it; DCH/XML avoid this receiver conversion')


def component_orientation(part) -> int:
    """ASC's legacy orientation is a normalized count of quarter turns."""
    angle = part.child('Angle')
    if angle is None or len(angle.values) != 1:
        raise ValueError('a component requires one angle to project orientation')
    from ...model.angles import (quarter_turns)
    return quarter_turns(angle.values[0])


def model3d_arguments(model) -> tuple:
    """Read the public ASC Model3D/pt tuple from named editable model data.

    XML supplies the names; ASC supplies the argument order. No private format
    record or source buffer is needed. Existing flat ASC records are also views.
    """
    flat = model.child('pt') or model.child('cl_pt')
    if flat is not None:
        return flat.arguments
    fields = []
    for name in ('Rotate', 'Offset', 'Zoom'):
        vector = model.child(name)
        if vector is None:
            raise ValueError(f'{model.path}: missing {name}')
        fields.extend(vector.child(axis) for axis in ('X', 'Y', 'Z'))
    fields.extend(model.child(name) for name in ('Mirror', 'NoSearch', 'Units',
        'IPC_XOff', 'IPC_YOff', 'AutoHeight', 'AutoColor', 'Type', 'KeepPins'))
    if any(field is None or len(field.arguments) != 1 or field.children() for field in fields):
        raise ValueError(f'{model.path}: incomplete 3D placement data')
    return tuple(field.arguments[0] for field in fields)
