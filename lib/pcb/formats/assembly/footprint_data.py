"""Consume footprint syntax bookkeeping before exposing current design data."""
from ..errors import PcbError
from ...model.library_relations import DRAWING_PAD_ROLE


def consume_drawing_pads(footprint):
    """Resolve saved local selectors before pad order becomes model order."""
    links = []
    for shape in footprint.shapes.values():
        field = shape.child('PadId')
        if field is None:
            continue
        key = field.values[0]
        if key >= 0:
            pad = footprint.pads.get(key)
            if pad is None:
                raise PcbError(f'{shape.path}: unresolved footprint drawing pad selector {key}')
            links.append((shape, pad))
        field.detach()
    return links


def bind_drawing_pads(document, links):
    for shape, pad in links:
        document.references.bind(shape, pad, role=DRAWING_PAD_ROLE, preserve=True)


def consume_paste_counts(pattern):
    for owner in (pattern, *pattern.select('Pads/Pad')):
        for name in ('PadMask_TopSegments', 'PadMask_BotSegments'):
            source = owner.child(name)
            if source is None or not source.arguments:
                continue
            if (len(source.arguments) != 1 or type(source.values[0]) is not int
                    or source.arguments[0].unit or source.values[0] != len(source.children())
                    or any(row.kind != 'pt' for row in source.children())):
                raise PcbError(f'{source.path}: paste segment count does not match current rows')
            source.set_values()
