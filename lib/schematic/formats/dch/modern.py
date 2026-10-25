"""Schema-40 drawing and label extensions, in our document vocabulary."""
from decimal import Decimal
import math

from ....common.model import (SourceSpan)
from ....common.drawing_codec import read_text_lines as _text_lines
from ....common.footprint_codec import read_pattern_extensions
from ....common.symbol_codec import read_symbol_extensions
from ...model.traversal import (placed_components, cached_definitions)


def _snap_angle(value):

    # This is not modulo normalization: it preserves arbitrary full turns.
    degrees = float(value) * 180.0 / math.pi
    if abs(degrees - math.trunc(degrees)) < 0.001:
        return Decimal(str(round(degrees) * math.pi / 180.0))
    return value


def _angle(r, parent, name):
    node = r.field(parent, name, "number", replace=True)
    stored = node.values[0]
    node.set_values(_snap_angle(stored))
    return node


def _label(r, parent, name, integer_count):
    node = r.record(parent, name, *('integer',)*integer_count, 'number', 'number', 'number')
    node.set_argument(integer_count+2, _snap_angle(node.values[-1]))
    return node


def pattern_properties(r, pattern):
    """Read shared footprint data with schematic angle and origin policy."""
    read_pattern_extensions(r, pattern, angle_reader=_angle)
    common = pattern.one("OriginCommon")
    if common.values[0] == 2:
        common.set_values(1)


def symbol_properties(r, part, *, placed):
    read_symbol_extensions(r, part, placed=placed, angle_reader=_angle)


def read_drawing_extensions(r, schematic):
    if r.header.version < 40:
        return
    for name, size in (("ShowRefDes_Global", 3), ("ShowName_Global", 3), ("ShowValue_Global", 2),
                       ("ShowManufacturer_Global", 2), ("ShowDatasheet_Global", 2)):
        schematic.add(name, *(r.argument('integer') for _ in range(size)))
    fields = schematic.add("ShowUserfield_Global")
    for _ in range(r.count("global user-field labels")):
        fields.add("pt", r.argument('text'), r.argument('text'), r.argument('integer'), r.argument('integer'))
    for part in placed_components(schematic):
        r.field(part, "CustomMarkingFont", "boolean")
        r.field(part, "MarkingFontSize", "integer")
        r.field(part, "MarkingFontAll", "boolean")
        for name, size in (("ShowRefDes", 5), ("ShowName", 5), ("ShowValue", 4),
                           ("ShowManufacturer", 4), ("ShowDatasheet", 4)):
            _label(r, part, name, size)
        for field in part.child("UserFields").children("UserField"):
            start = r.pos
            integers = tuple(r.argument('integer') for _ in range(4))
            x, y, angle = r.argument('number'), r.argument('number'), r.argument('number')
            field.set_values(*field.arguments, *integers, x, y, _snap_angle(angle.value))
            field.annotations["label_source"] = SourceSpan("dch", start, r.pos, r.source)
        pattern_properties(r, part.child("Pattern"))
        symbol_properties(r, part, placed=True)
    for shape in schematic.child("Shapes").children("Shape"):
        _angle(r, shape, "TextAngle")
        for name in ("TextHorz", "TextVert", "TextAlign"):
            r.field(shape, name, "integer")
        r.field(shape, "LineSpacing", "number")
        _text_lines(r, shape)
    for table in schematic.child("Tables").children("Table"):
        r.field(table, "DefLineSpacing", "number")
        for cell in table.child("Cells").children("Cell"):
            r.field(cell, "LineSpacing", "number")
    for page in schematic.child("Pages").children("Page"):
        for grid in page.child("TitleBlocks").children("TitleBlock"):
            for cell in grid.child("Contents").children("Content"):
                r.field(cell, "LineSpacing", "number")
    for definition in cached_definitions(schematic):
        pattern_properties(r, definition.child("Pattern"))
        symbol_properties(r, definition.child("Part"), placed=False)
