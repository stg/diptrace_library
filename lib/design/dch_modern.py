"""Schema-40 drawing and label extensions, in our document vocabulary."""
from decimal import Decimal
import math

from .model import SourceSpan
from .dch_records import placed_components, cached_definitions


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


def _text_lines(r, shape):
    start = r.pos
    lines = shape.child("TextLine")
    if lines is None:
        lines = shape.add("TextLine")
    else:
        for child in tuple(lines.children()):
            child.detach()
    for _ in range(r.count("shape text lines")):
        lines.add("pt", r.argument('text'))
    lines.source = SourceSpan("dch", start, r.pos, r.source)


def _replace_point_coordinates(r, shape):
    # The extension has the same point count as the earlier compatibility
    # array; it does not serialize a second count here.
    for point in shape.child("Points_New").children("pt"):
        start = r.pos
        point.set_values(r.argument('number'), r.argument('number'))
        point.source = SourceSpan("dch", start, r.pos, r.source)


def _terminals(r, parent):
    count = r.count("pad terminals")
    parent.add("PadTerminalCount", count)
    for index in range(count):
        node = parent.add("PadTerminal", index)
        r.field(node, "Type", "integer")
        for name in ("X", "Y"):
            r.field(node, name, "number")
        _angle(r, node, "Angle")
        for name in ("ShapeWidth", "ShapeHeight", "ShapeCorner"):
            r.field(node, name, "number")
        points = node.add("ShapePoints")
        for _ in range(r.count("terminal polygon points")):
            points.add("pt", r.argument('number'), r.argument('number'))


def _mask_segments(r, parent):
    for name in ("PadMask_TopSegments", "PadMask_BotSegments"):
        count = r.count("pad mask segments")
        node = parent.add(name, count)
        for _ in range(count):
            node.add("pt", *(r.argument('number') for _ in range(4)))


def _groups(r, parent, name):
    groups = parent.add(name)
    for _ in range(r.count("drawing groups")):
        groups.add("pt", r.argument('boolean'), r.argument('integer'), r.argument('number'), r.argument('number'))


def pattern_properties(r, pattern):
    """Pattern properties."""
    for name in ("OriginCross", "OriginCircle"):
        r.field(pattern, name, "boolean")
    common = r.field(pattern, "OriginCommon", "integer")
    r.field(pattern, "OriginCourtyard", "integer")
    if common.values[0] == 2:
        common.set_values(1)
    for name in ("Name_Description", "Name_Unique", "RecoveryCode"):
        r.field(pattern, name, "text")
    for name in ("RecoveryCode_Generator", "RecoveryCode_Model"):
        r.field(pattern, name, "boolean")
    r.field(pattern, "Pattern_Manufacturer", "text")
    for name in ("PadCorner", "PadShape_X", "PadShape_Y"):
        r.field(pattern, name, "number")
    _terminals(r, pattern)
    for name in ("TopMask_State", "BotMask_State", "TopPaste_State", "BotPaste_State"):
        r.field(pattern, name, "integer")
    for name in ("CustomSwell_New", "CustomShrink_New", "PadMask_Percent", "PadMask_EdgeGap", "PadMask_SegmentGap", "PadMask_SegmentSide"):
        r.field(pattern, name, "number")
    _mask_segments(r, pattern)
    for pad in pattern.child("Pads").children("Pad"):
        r.field(pad, "Group", "integer")
        r.field(pad, "PadCorner", "number")
        _angle(r, pad, "PadAngle")
        for name in ("PadShape_X", "PadShape_Y"):
            r.field(pad, name, "number")
        _terminals(r, pad)
        for name in ("PadMask_Percent", "PadMask_EdgeGap", "PadMask_SegmentGap", "PadMask_SegmentSide"):
            r.field(pad, name, "number")
        _mask_segments(r, pad)
    for shape in pattern.child("Shapes").children("Shape"):
        _replace_point_coordinates(r, shape)
        _angle(r, shape, "TextAngle")
        for name in ("TextHorz", "TextVert", "TextAlign"):
            r.field(shape, name, "integer")
        r.field(shape, "LineSpacing", "number")
        _text_lines(r, shape)
        r.field(shape, "AllLayers", "boolean")
        r.field(shape, "Group", "integer")
    for hole in pattern.child("Holes").children("Hole"):
        hole.set_values(*hole.arguments, r.argument('integer'))
    for dimension in pattern.child("Dimensions").children("Dimension"):
        r.field(dimension, "Group", "integer")
    _groups(r, pattern, "Pattern_Groups")
    model = pattern.child("Model3D")
    for name, kind in (('IPC_XOff', 'number'), ('IPC_YOff', 'number'),
                       ('AutoHeight', 'number'), ('AutoColor', 'color'), ('Type', 'integer')):
        r.field(model, name, kind)


def symbol_properties(r, part, *, placed):
    for pin in part.child("Pins").children("Pin"):
        r.field(pin, "Group", "integer")
    for shape in part.child("Shapes").children("Shape"):
        _angle(r, shape, "TextAngle")
        for name in ("TextHorz", "TextVert", "TextAlign"):
            r.field(shape, name, "integer")
        r.field(shape, "LineSpacing", "number")
        _text_lines(r, shape)
        r.field(shape, "Group", "integer")
        if placed:
            for name in ("ShowPart", "MarkingGenerated"):
                r.field(shape, name, "boolean", replace=True)
    if not placed:
        _groups(r, part, "Groups")


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
