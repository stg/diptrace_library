"""Append-only DCH schema extensions, expressed in public document concepts."""
from decimal import Decimal

from ....common.model import (SourceSpan)
from ....common.footprint_codec import read_pad_mask_states
from ...model.traversal import (placed_components, footprints)


def _pad_states(r, pattern):
    for pad in pattern.child("Pads").children("Pad"):
        read_pad_mask_states(r, pad, extended=True)


def read_common_extensions(r, schematic, document):
    """Read common extensions."""
    classes = schematic.child("NetClasses").children("NetClass")
    pairs = schematic.add("DifferentialPairs")
    if r.header.version >= 35:
        for node in classes:
            node.set_values(*node.arguments, *(r.argument('number') for _ in range(5)))
            node.annotations.pop("incomplete", None)
        for _ in range(r.count("differential pairs")):
            start = r.pos
            enabled, name = r.argument('boolean'), r.argument('text')
            node = pairs.add("DifferentialPair", name, enabled, r.argument('integer'), r.argument('integer'), r.argument('integer'), r.argument('boolean'), r.argument('color'))
            node.source = SourceSpan("dch", start, r.pos, r.source)
    else:

        for node in classes:
            node.set_values(*node.arguments, *(Decimal(x) for x in (-1, 30, 6, 6, 30)))
            node.annotations.pop("incomplete", None)
    if r.header.version >= 36:
        for name in ("Xpos", "Ypos"):
            r.field(document.root, name, "number", replace=True)
        for page in schematic.child("Pages").children("Page"):
            for name in ("PageXPos", "PageyPos"):
                r.field(page, name, "number", replace=True)
    parts = placed_components(schematic)
    if r.header.version >= 37:
        for part in parts:
            for pin in part.child("Pins").children("Pin"):
                r.field(pin, "SignalDelay", "number")
    else:
        for part in parts:
            for pin in part.child("Pins").children("Pin"):
                pin.add("SignalDelay", Decimal(0)).annotations["default_for_version"] = r.header.version
    if r.header.version >= 38:
        for pattern in footprints(schematic):
            _pad_states(r, pattern)
    if r.header.version >= 39:
        node = r.field(schematic.child("Settings"), "GridSize", "number", replace=True)
        divisor = r.integer()
        node.set_values(node.values[0] / max(1, divisor))
