"""Owned symbol identities over the common pin/drawing vocabulary."""
from dataclasses import replace

from ...common import symbol_records
from ...common.relationship_fields import optional_reference_fields
from ...common.schema import Child, Record, MISSING
from ...common.symbol_text_style import TEXT_FIELDS
from ...common.unplaced_footprint_records import grouped
from .text_fields import SELECTION


GROUP_ROLE = 'component-symbol-group'
PAD_ROLE = 'component-pin-pad'
_pad_fields = optional_reference_fields('Pad', 'PadId', PAD_ROLE, offset=1)
PIN = grouped(replace(symbol_records.PIN, name='LibraryPin', fields={
    **{name: field for name, field in symbol_records.PIN.fields.items() if name != 'Number'},
    **_pad_fields,
    'StringNumber': replace(symbol_records.PIN.fields['StringNumber'],
        description='Authored symbol pin label; independent of the selected physical pad label.'),
    'PinNumRotate': replace(symbol_records.PIN.fields['PinNumRotate'], kind='integer', unit='',
        description='Pin-number orientation choice in the standalone symbol.'),
    'PinNameRotate': replace(symbol_records.PIN.fields['PinNameRotate'], kind='integer', unit='',
        description='Pin-name orientation choice in the standalone symbol.'),
    'Number': replace(_pad_fields['PadId'], name='Number',
        description='Calculated pad key; edit Pad to change its identity.')
}), role=GROUP_ROLE)
DRAWING = grouped(replace(symbol_records.DRAWING, name='LibrarySymbolDrawing', fields={
    **{name: replace(field, required=False, default=MISSING) if name in TEXT_FIELDS or name == 'PenWidth' else field
       for name, field in symbol_records.DRAWING.fields.items()
       if name not in ('ShowPart', 'MarkingGenerated')},
    'FontType': replace(symbol_records.DRAWING.fields['FontType'],
        required=False, default=MISSING,
        description='Placement text choice; values20+ follow UserField identity. TextLine remains authored.'),
    'UserField': SELECTION,
    'PenWidth': replace(symbol_records.DRAWING.fields['PenWidth'], required=False, default=MISSING,
        description='Geometric drawing stroke; text uses FontWidth and has no PenWidth.'),
}), role=GROUP_ROLE)
PINS = Record('LibraryPins', {}, children={'Pin': Child('Pin', PIN.name, maximum=None)})
DRAWINGS = Record('LibrarySymbolDrawings', {}, children={'Shape': Child('Shape', DRAWING.name, maximum=None)})


def part_of(node):
    while node is not None:
        if node.kind == 'Part':
            return node
        node = node.parent
    return None
