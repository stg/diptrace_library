"""ASC scalar projection, separate from stored document values.

The generic ASC editor preserves source spelling. Conversion from DCH instead
needs the format export rules: four-place binary floating-point rounding and
the quoted-text sanitizer. Applying these rules never mutates the document.
"""
from decimal import Decimal
import math
from ....common.asc_text import quoted_text, project_text as _project_text





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
    return _project_text(document, encoding=encoding, report=report,
                         receiver_normalizes=_receiver_normalized_text, redundant_text=_redundant_cell_text)


def component_orientation(part) -> int:
    """ASC's legacy orientation is a normalized count of quarter turns."""
    angle = part.child('Angle')
    if angle is None or len(angle.values) != 1:
        raise ValueError('a component requires one angle to project orientation')
    from ...model.angles import (quarter_turns)
    return quarter_turns(angle.values[0])
