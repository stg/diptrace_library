"""Versioned DCH input adapter into our own public document model."""
from __future__ import annotations

from decimal import Decimal
import hashlib
import math
from pathlib import Path

# Kept as module exports for existing callers of the DCH adapter.
from .binary import (Cursor, DchError, Header, MIN_VERSION, MAX_KNOWN_VERSION, UnsupportedVersionError, read_header)
from .records import (COMPONENT_PLACEMENT, PIN_FONT)
from .data import (stored_data)
from ...model.document import (Document)
from ....common.model import (Element, IncompleteDocumentError, SourceSpan, Value)
from ....common.binary_records import RecordReader
from ....common.numbers import decimal_scale
from ....common.footprint_codec import (read_holes, read_model, read_parameters as _pattern_parameters,
                                       read_pad_geometry, read_pad_mask_states)
from ....common.dimension_codec import read_dimensions
from ....common.title_block_codec import read_title_block
from ....common.catalog_codec import read_category_types, read_possible_names

_OLD_TEXT_ALIGNMENT = {0: 1, 1: 2, 2: 5, 3: 7, 5: 3}


class Reader(RecordReader, Cursor):
    """Populate our document elements from named wire fields."""
    source_format = 'dch'

    def record_definition(self, parent):
        from ...model.definitions import definition
        return definition(parent)

def _preamble(r: Reader, doc: Document) -> tuple[Element, int]:
    r.add_into(doc.root, "Source", "DipTrace-Schematic", 46)
    # Units are a separate format export setting; do not invent a value here.
    for kind, name in [("number", "Scale"), ("integer", "Xpos"), ("integer", "Ypos")]:
        node = r.field(doc.root, name, kind)
        if name == "Scale":
            stored = node.values[0]
            factor = min(Decimal(1000), max(Decimal('0.01'), stored))
            percent = decimal_scale(factor, 2)
            node.set_argument(0, Value(percent, 'number', '%', source=node.arguments[0].source))
    schematic = r.add(doc.root, "Schematic")
    r.field_into(schematic, "ActiveSheet", "integer")
    pages = r.add(schematic, "Pages")
    for _ in range(r.count("pages")):
        start = r.pos
        page = r.add(pages, "Page", r.argument('text'))
        page.source = SourceSpan("dch", start, r.pos, r.source)

        # The prefix repeats PageType; the later page layout is authoritative.
        r.integer()
        # Persistent page identity arrives in the schema-33 extension.
        if r.header.version <= 32:
            r.add_into(page, "PageHiddenId", 0)
    pictures = r.integer()
    if pictures < 0:
        raise DchError('negative legacy picture resource count')
    # Only the count is stored here. Numbered picture companions are external
    # to this single input; current layouts use file-backed picture properties.
    if r.header.version < 42 and pictures:
        doc.diagnostics.append('Legacy companion picture filenames are unavailable '
                               f'in the DCH byte stream (count={pictures})')
    for name in ("ShowText", "TextAlign", "ShowText2", "TextAlign2"):
        node = r.field(schematic, name, "integer")
        if r.header.version < 40 and name in ("TextAlign", "TextAlign2"):
            original = node.values[0]
            node.set_argument(0, _OLD_TEXT_ALIGNMENT.get(original, original))
    for kind, name in [("boolean", "HidePower"), ("number", "OriginX"), ("number", "OriginY"),
                       ("text", "FieldName1"), ("text", "FieldName2"), ("boolean", "PartFontVector"),
                       ("number", "PartFontWidth"), ("number", "PartFontScale")]:
        r.field_into(schematic, name, kind)
    classes = r.add(schematic, "NetClasses")
    for _ in range(r.count("net classes")):
        node = r.add(classes, "NetClass", r.argument('text'), r.argument('integer'), r.argument('number'), r.argument('number'), r.argument('integer'))
        node.annotations["incomplete"] = "remaining class settings occur later in the file"
    return schematic, r.count("components")


def _component_head(r: Reader, components: Element) -> Element:
    start = r.pos
    part = r.add(components, "Part")
    r.fields(part, COMPONENT_PLACEMENT)
    name, ref, value, base_ref, base_name = [r.argument('text') for _ in range(5)]
    part.set_values(name, ref)
    for key, val in (("Value", value), ("BaseName", base_name), ("BaseRefDes", base_ref)):
        r.add_into(part, key, val)
    for name in ("ShowText", "TextAlign"):
        r.field_into(part, name, "integer")
    r.field_into(part, "LockProperties", "boolean")
    for kind, name in [("integer", "PartNumber"), ("integer", "PartType"),
                       ("text", "PartName"), ("text", "PartDescriptor"), ("boolean", "AllowParts"),
                       ("integer", "ShowText2"), ("integer", "TextAlign2"), ("integer", "ShowNumbers")]:
        r.field_into(part, name, kind)
    for name in ("TextPosX", "TextPosY", "TextPosX2", "TextPosY2"):
        r.field_into(part, name, "number")
    r.field_into(part, "PartString", "text")
    r.field_into(part, "HiddenId", "integer")
    fields = r.add(part, "UserFields")
    for _ in range(r.count("component user fields")):
        r.add_into(fields, "UserField", r.argument('text'), r.argument('text'), r.argument('integer'))
    for name in ("FieldIndex1", "FieldIndex2"):
        r.field_into(part, name, "integer")
    r.field_into(part, "Locked", "boolean")
    angle = r.field(part, "Angle", "number")
    if not r.header.angles_in_degrees:
        radians = angle.values[0]
        angle.set_argument(0, Decimal(str(round(float(radians) * 180 / math.pi, 4))))
    for kind, name in [("text", "LibPath"), ("integer", "ModelType")]:
        r.field_into(part, name, kind)
    part.source = SourceSpan("dch", start, r.pos, r.source)
    part.annotations["incomplete"] = "component body follows this decoded scalar prefix"
    return part


def _component_pins(r: Reader, part: Element):
    """format gates for this prefix all precede minimum schema 29."""
    model_body = r.add(part, "ModelBody")
    for _ in range(r.count("model text lines")):
        r.add_into(model_body, "Line", r.argument('text'))
    r.field_into(part, "ModelString", "text")
    r.field_into(part, "Datasheet", "text")
    r.field_into(part, "HorzFlip", "boolean")
    r.field_into(part, "VertFlip", "boolean")
    pins = r.add(part, "Pins")
    for index in range(r.count("pins")):
        start = r.pos
        pin = r.add(pins, "Pin", index)
        r.field_into(pin, "Enabled", "boolean")
        for name in ("Type", "Orientation", "Number", "NetNumber"):
            r.field_into(pin, name, "integer")
        pin.set_values(index, r.argument('number'), r.argument('number'))
        r.field_into(pin, "Length", "number")
        for name in ("Name", "StringNumber"):
            r.field_into(pin, name, "text")
        for name in ("FConnect", "ShowName"):
            r.field_into(pin, name, "boolean")
        for name in ("PinNumXShift", "PinNumYShift", "PinNameXShift", "PinNameYShift"):
            r.field_into(pin, name, "number")
        r.field_into(pin, "ElectricType", "integer")
        for name in ("Hidden", "Locked"):
            r.field_into(pin, name, "boolean")
        r.field_into(pin, "ModelSig", "text")
        r.field_into(pin, "NoConnect", "boolean")
        r.fields(pin, PIN_FONT)
        pin.source = SourceSpan("dch", start, r.pos, r.source)
    part.annotations["incomplete"] = "component shapes and following fields are not decoded"
    return r.count("component shapes")


def _component_shapes(r: Reader, part: Element, *, count, placed=True):
    shapes = r.add(part, "Shapes")
    for index in range(count):
        start = r.pos
        shape = r.add(shapes, "Shape", index)
        if not placed:
            # Cached symbol drawings never serialize the placed-only flag.
            r.add_into(shape, 'ShowPart', False)
        r.field_into(shape, "Enabled", "boolean")
        r.field_into(shape, "Orientation", "integer")
        kind = r.field(shape, "Type", "integer")
        # Only the placed-symbol reader recognizes the old marking tag. Cached
        # symbols use the same field layout but keep their ordinary type value.
        generated = placed and kind.values[0] == 700
        if generated:
            kind.set_argument(0, 10)
        r.field_into(shape, "FontSize", "integer")
        r.field_into(shape, "FontColor", "color")
        r.field_into(shape, "FontType", "integer")
        r.field_into(shape, "FontName", "text")
        r.field_into(shape, "Name", "text")
        r.add_into(r.add(shape, 'TextLine'), 'pt', shape.child('Name').arguments[0])
        r.field_into(shape, "PenWidth", "number")
        # The >=40 format stores the editable geometry. format export also
        # projects historical text bounds, which require its layout rules.
        points = r.add(shape, "Points_New" if r.header.version >= 40 else "Points")
        for _ in range(r.count("shape points")):
            r.add_into(points, "pt", r.argument('number'), r.argument('number'))
        r.field_into(shape, "Locked", "boolean")
        r.field_into(shape, "VectorFont", "boolean")
        r.field_into(shape, "FontWidth", "number")
        r.field_into(shape, "FontScale", "number")
        r.add_into(shape, "MarkingGenerated", generated)
        shape.source = SourceSpan("dch", start, r.pos, r.source)
        shape.annotations["incomplete"] = "format text/layout projection and derived ASC fields remain to be mapped"
    part.annotations["incomplete"] = "component suffix after its shape array remains to be decoded"


def _component_pattern(r: Reader, part: Element):
    """Component pattern."""
    start = r.pos
    pattern = r.add(part, "Pattern")
    connections = r.add(pattern, "InternalConnections")
    for _ in range(r.count("footprint internal connections")):
        r.add_into(connections, "IntCon", r.argument('integer'), r.argument('integer'))
    _pattern_parameters(r, pattern)
    for name in ("Origin_X", "Origin_Y"):
        r.field_into(part, name, "number")
    r.field_into(part, "ShowOrigin", "boolean")
    fields = r.add(pattern, "UserFields")
    for _ in range(r.count("footprint user fields")):
        r.add_into(fields, "UserField", r.argument('text'), r.argument('text'), r.argument('integer'))
    points = r.add(pattern, "PadPoints")
    for _ in range(r.count("footprint default pad points")):
        r.add_into(points, "pt", r.argument('number'), r.argument('number'))
    pattern.source = SourceSpan("dch", start, r.pos, r.source)
    pad_count = r.count("footprint pads")
    pattern.annotations["incomplete"] = "footprint pads and later settings remain to be decoded"
    part.annotations["incomplete"] = "component footprint body and later fields remain to be decoded"
    return pattern, pad_count




def _pattern_pads(r: Reader, pattern: Element, *, count):
    """Extended pad properties occur later in the component. These nodes remain
    incomplete until those extensions and the format compatibility projection
    have been applied.
    """
    pads = r.add(pattern, "Pads")
    for index in range(count):
        start = r.pos
        inverted = r.argument('boolean')
        pad = r.add(pads, "Pad", index)
        number = r.argument('integer')
        x, y = r.argument('number'), r.argument('number')
        name, detail = r.argument('text'), r.argument('text')
        pad.set_values(index, name, detail, x, y)
        r.add_into(pad, "Number_New", number)
        r.add_into(pad, "PadAngle", Decimal(str(math.pi/2)) if inverted.value else Decimal(0))
        read_pad_geometry(r, pad)
        r.field_into(pad, "Locked", "boolean")
        r.field_into(pad, "Sided", "boolean")
        read_pad_mask_states(r, pad)
        for name in ("CustomSwell_New", "CustomShrink_New"):
            r.field_into(pad, name, "number")
        pad.source = SourceSpan("dch", start, r.pos, r.source)
        pad.annotations["incomplete"] = "extended pad fields and compatibility projection remain"
    pattern.annotations["incomplete"] = "footprint shapes and later fields remain to be decoded"


def _pattern_graphics(r: Reader, pattern: Element):
    """Graphics use our nested shape representation. ASC flattens footprint
    shape properties into successive sibling records; that projection is a
    writer concern, not a reason to duplicate its old memory structures here.
    """
    shapes = r.add(pattern, "Shapes")
    for index in range(r.count("footprint shapes")):
        start = r.pos
        shape = r.add(shapes, "Shape", index)
        r.field_into(shape, "Type", "integer")
        if r.header.version < 40:
            r.record(stored_data(shape), 'CompatibilityGeometry', *('number',)*6)
        else:
            for _ in range(6):
                r.number()  # Superseded by the physical-coordinate extension.
        r.field_into(shape, "Locked", "boolean")
        r.field_into(shape, "Layer", "integer")
        r.add_into(r.add(shape, "TextLine"), "pt", r.argument('text'))
        r.field_into(shape, "FontName", "text")
        r.field_into(shape, "VectorFont", "boolean")
        # The flat ASC tuple does not label these arguments. Public DCHXML

        r.field_into(shape, "FontSize", "integer")
        for name in ("FontScale", "FontWidth"):
            r.field_into(shape, name, "number")
        if r.header.version < 40:
            r.field_into(stored_data(shape), 'TextOrientation', 'integer')
        else:
            r.integer()  # Current TextAngle arrives in the extension.
        r.field_into(shape, 'TextShow', 'integer')
        r.field_into(shape, "Width", "number")
        count = r.count("footprint shape points")
        points = r.add(shape, "Points_New")
        r.points(points, count)
        shape.source = SourceSpan("dch", start, r.pos, r.source)
        shape.annotations["incomplete"] = "extended geometry and legacy ASC projection remain"
    holes = read_holes(r, pattern)
    for hole in holes.children():
        hole.annotations["incomplete"] = "hole group is stored in the later extension"
    dimensions = read_dimensions(r, pattern)
    for dimension in dimensions.children():
        dimension.annotations["incomplete"] = "dimension group is stored in the later extension"


def _pattern_model(r: Reader, pattern: Element):
    model = read_model(r, pattern)
    model.annotations["incomplete"] = "later 3D settings and ASC projection remain"
    pattern.annotations["incomplete"] = "later footprint extensions and ASC projection remain"


def _page_connectors(r: Reader, schematic: Element):
    connectors = r.add(schematic, "PageConnectors")
    for _ in range(r.count("page connectors")):
        start = r.pos
        node = r.add(connectors, "PageConnector")
        for name in ("Enabled", "Selected", "Connected"):
            r.field_into(node, name, "boolean")
        x, y = r.argument('number'), r.argument('number')
        for name in ("Page", "BusNumber", "Number", "Region", "Group"):
            r.field_into(node, name, "integer")
        node.set_values(r.argument('text'), x, y)
        r.field_into(node, "Locked", "boolean")
        node.source = SourceSpan("dch", start, r.pos, r.source)


def _schematic_graphics(r: Reader, schematic: Element):
    shapes = r.add(schematic, "Shapes")
    for index in range(r.count("schematic shapes")):
        start = r.pos
        shape = r.add(shapes, "Shape", index)
        for name in ("Enabled", "Selected"):
            r.field_into(shape, name, "boolean")
        r.field_into(stored_data(shape), 'Orientation', 'integer')
        for name in ("Type", "FontSize"):
            r.field_into(shape, name, "integer")
        for name in ("FontColor", "Color", "BrushColor"):
            r.field_into(shape, name, "color")
        for name in ("FontType", "Page", "Group"):
            r.field_into(shape, name, "integer")
        r.field_into(shape, "PenWidth", "number")
        r.field_into(shape, "FontName", "text")
        r.add_into(r.add(shape, "TextLine"), "pt", r.argument('text'))
        bitmap = r.field(shape, "BitmapIndex", "integer")

        # Earlier pictures can still need their external resource table. Later
        # file-backed drawings do not use this transient bitmap-cache index.
        if r.header.version>=42 or shape.scalar('Type')!=11:
            bitmap.set_argument(0, -1)
        points = r.add(shape, "Points_New" if r.header.version >= 40 else "Points")
        for _ in range(r.count("schematic shape points")):
            r.add_into(points, "pt", r.argument('number'), r.argument('number'))
        for name in ("RelatedNet", "RelatedBus"):
            r.field_into(shape, name, "integer")
        r.field_into(shape, "Locked", "boolean")
        r.field_into(shape, "VectorFont", "boolean")
        for name in ("FontWidth", "FontScale"):
            r.field_into(shape, name, "number")
        shape.source = SourceSpan("dch", start, r.pos, r.source)
        shape.annotations["incomplete"] = "later drawing fields and format layout projection remain"


def _nets(r: Reader, schematic: Element):
    nets = r.add(schematic, "Nets")
    for _ in range(r.count("nets")):
        start = r.pos
        net = r.add(nets, "Net")
        r.field_into(net, "Enabled", "boolean")
        r.boolean()  # Obsolete net selection slot; not a current property.
        for name in ("UniteByName", "ConnectPinByName"):
            r.field_into(net, name, "boolean")
        for name in ("ActiveLine", "ActivePoint", "Number"):
            r.field_into(net, name, "integer")
        r.integer()  # Discarded compatibility slot.
        net.set_values(r.argument('text'))
        for name in ("Width", "Clearance"):
            r.field_into(net, name, "number")
        r.field_into(net, "NetClass", "integer")
        r.field_into(net, "Global", "boolean")
        parts = r.add(net, "Parts")
        for _ in range(r.count("net pin references")):
            r.record(parts, 'pt', 'integer', 'integer')
        lines = r.add(net, "Lines")
        for _ in range(r.count("net lines")):
            line_start = r.pos
            line = r.add(lines, "Line")
            for name in ("Connect1", "Connect2", "ConnectL1", "ConnectL2", "ConnectB1", "ConnectB2",
                         "Page", "ConnectMode1", "ConnectMode2", "NetNumber", "Region", "Number"):
                r.field_into(line, name, "integer")
            r.field_into(line, "Hidden", "boolean")
            points = r.add(line, "Points")
            for _ in range(r.count("wire points")):
                r.record(points, 'pt', 'number', 'number', 'integer')
            r.field_into(line, "Selected", "boolean")
            r.field_into(line, "Group", "integer")
            r.field_into(line, "CanUnhide", "boolean")
            r.field_into(line, "Arrows", "integer")
            line.source = SourceSpan("dch", line_start, r.pos, r.source)
        for name in ("Locked", "CustomColor"):
            r.field_into(net, name, "boolean")
        r.field_into(net, "WireColor", "color")
        net.source = SourceSpan("dch", start, r.pos, r.source)
        net.annotations["incomplete"] = "later net extension fields remain"


def _buses_and_groups(r: Reader, schematic: Element):
    """Buses and groups."""
    buses = r.add(schematic, "Buses")
    for _ in range(r.count("buses")):
        start = r.pos
        bus = r.add(buses, "Bus")
        r.field_into(bus, "Enabled", "boolean")
        r.boolean()  # Obsolete bus selection slot; not a current property.
        for name in ("ActiveLine", "ActivePoint", "Number", "Region"):
            r.field_into(bus, name, "integer")
        r.integer()  # Discarded compatibility slot.
        bus.set_values(r.argument('text'))
        nets = r.add(bus, "Nets")
        for _ in range(r.count("bus nets")):
            r.add_into(nets, "pt", r.argument('integer'))
        lines = r.add(bus, "Lines")
        for _ in range(r.count("bus lines")):
            line_start = r.pos
            line = r.add(lines, "Line")
            for name in ("Connect1", "Connect2", "ConnectL1", "ConnectL2", "ConnectB1", "ConnectB2",
                         "Page", "ConnectMode1", "ConnectMode2", "BusNumber", "Region", "Number"):
                r.field_into(line, name, "integer")
            points = r.add(line, "Points")
            for _ in range(r.count("bus wire points")):
                r.add_into(points, "pt", r.argument('number'), r.argument('number'), r.argument('integer'))
            r.field_into(line, "Selected", "boolean")
            r.field_into(line, "Group", "integer")
            line.source = SourceSpan("dch", line_start, r.pos, r.source)
        r.field_into(bus, "Locked", "boolean")
        numbers = r.add(bus, "Numbers")
        for _ in range(r.count("bus numbers")):
            r.add_into(numbers, "pt", r.argument('integer'))
        bus.source = SourceSpan("dch", start, r.pos, r.source)
    groups = r.add(schematic, "Groups")
    for _ in range(r.count("groups")):
        start = r.pos
        group = r.add(groups, "Group")
        for name in ("Enabled", "Selected"):
            r.field_into(group, name, "boolean")
        group.set_values(r.argument('integer'), r.argument('number'), r.argument('number'))
        group.source = SourceSpan("dch", start, r.pos, r.source)


def _title_grid(r: Reader, parent: Element, index: int):
    read_title_block(r, parent, index)


def _page_layouts(r: Reader, schematic: Element):
    pages = schematic.child("Pages").children("Page")
    # The format loop uses the earlier page-array length; the repeated stored

    r.integer()  # Repeated framing count; the page array determines this loop.
    for page in pages:
        start = r.pos
        zones = r.add(page, "Zones")
        for name in ("PageWidth", "PageHeight"):
            r.field_into(page, name, "number")
        for name in ("FLeft", "FTop", "FRight", "FBottom"):
            r.field_into(page, name, "number")
        titles = r.add(page, "TitleBlocks")
        for index in range(6):
            _title_grid(r, titles, index)
        zones.set_values(r.argument('boolean'))
        for name in ("HorzZones", "VertZones", "ZoneStandard"):
            r.field_into(page, name, "integer")
        r.field_into(page, "ZoneFontName", "text")
        r.field_into(page, "ZoneFontSize", "integer")
        r.field_into(page, "ZoneBorder", "boolean")
        for name in ("HorzZoneBorder", "VertZoneBorder"):
            r.field_into(page, name, "number")
        for name in ("PageXPos", "PageyPos"):
            r.field_into(page, name, "integer")
        scale = r.field(page, "PageScale", "number")
        original = scale.values[0]
        scale.set_argument(0, min(Decimal(1000), max(Decimal('0.01'), original)))
        # The border-zone font width uses the public XML FontLineWidth name.
        r.field_into(page, 'FontLineWidth', 'number')
        r.field_into(page, "PageType", "integer")
        if r.retain_source:
            page.annotations["layout_source"] = SourceSpan("dch", start, r.pos, r.source)


def _tables(r: Reader, schematic: Element):
    """Tables."""
    tables = r.add(schematic, "Tables")
    for _ in range(r.count("tables")):
        start = r.pos
        table = r.add(tables, "Table")
        for name in ("Enabled", "Selected"):
            r.field_into(table, name, "boolean")
        for name in ("Layer", "DefAlign", "DefFontSize", "Orientation", "Group", "Page"):
            r.field_into(table, name, "integer")
        r.field_into(table, "DefFontColor", "color")
        for name in ("DefCellWidth", "DefCellHeight", "X1", "Y1", "X2", "Y2"):
            r.field_into(table, name, "number")
        for name in ("DefFontName", "Name"):
            r.field_into(table, name, "text")
        columns = r.count("table columns")
        widths = r.add(table, "ColWidths")
        for _ in range(columns):
            r.add_into(widths, "pt", r.argument('number'))
        rows = r.count("table rows")
        heights = r.add(table, "RowHeights")
        for _ in range(rows):
            r.add_into(heights, "pt", r.argument('number'))
        # Every cell requires at least its boolean, three integers, color,
        # two strings, four numbers, a second boolean and two more numbers.
        if columns * rows > (len(r.data) - r.pos) // 42:
            raise DchError(f"table dimensions exceed remaining data at byte {r.pos:#x}")
        cells = r.add(table, "Cells")
        for column in range(columns):
            for row in range(rows):
                cell_start = r.pos
                cell = r.add(cells, "Cell")
                for kind, name in [("boolean", "FOrientation"), ("integer", "FontSize"),
                                   ("integer", "FontType"), ("integer", "Align"),
                                   ("color", "FontColor"), ("text", "Text"), ("text", "FontName")]:
                    r.field_into(cell, name, kind)
                cell.set_values(*(r.argument('number') for _ in range(4)))
                r.field_into(cell, "VectorFont", "boolean")
                for name in ("FontWidth", "FontScale"):
                    r.field_into(cell, name, "number")
                cell.source = SourceSpan("dch", cell_start, r.pos, r.source)
        for name in ("Locked", "DefVectorFont"):
            r.field_into(table, name, "boolean")
        for name in ("DefFontWidth", "DefFontScale"):
            r.field_into(table, name, "number")
        r.field_into(table, "HideBorder", "boolean")
        table.source = SourceSpan("dch", start, r.pos, r.source)
        table.annotations["incomplete"] = "later line-spacing settings and format cell-text projection remain"


def _settings(r: Reader, schematic: Element):
    """Settings."""
    settings = r.add(schematic, "Settings")
    r.field_into(settings, "GridSize", "number")
    r.field_into(settings, "OriginEnabled", "boolean")
    r.field_into(settings, "clAxis", "color")
    for name in ("BusConnectionFont", "PinNumberFont"):
        r.field_into(settings, name, "integer")
    for name in ("GridEnabled", "DisplayTitles", "DisplaySheet", "BusConNetName", "BusConNetNumber",
                 "ShowPinNumbers", "HidePinNumbers", "BusConAbove", "BusConBelow"):
        r.field_into(settings, name, "boolean")
    for name in ("BusLineWidth", "WireLineWidth", "TableLineWidth", "TitlesLineWidth", "NodeSize"):
        r.field_into(settings, name, "number")
    for name in ("UnitsMM", "UnitsMIL", "UnitsINCH", "ERC_PinType", "ERC_NotConnected", "ERC_SinglePin", "ERC_Short"):
        r.field_into(settings, name, "boolean")
    for name in ("ERC_VCCTemplate", "ERC_GNDTemplate"):
        r.field_into(settings, name, "text")
    if r.header.version >= 30:
        r.field_into(settings, "ERC_PinSuperimpose", "boolean")
    else:
        r.add_into(settings, "ERC_PinSuperimpose", True)


def _extensions_to_33(r: Reader, schematic: Element):
    """Extensions to 33."""
    parts = schematic.child("Components").children("Part")
    if r.header.version >= 31:
        for part in parts:
            model = part.child("Pattern").child("Model3D")
            r.field_into(model, 'Units', 'integer')
            for pin in part.child("Pins").children("Pin"):
                r.field_into(pin, "NetName", "text")
    else:
        for part in parts:
            r.add_into(part.child('Pattern').child('Model3D'), 'Units', -1)
            for pin in part.child("Pins").children("Pin"):
                r.add_into(pin, "NetName", "")
    if r.header.version >= 32:
        for part in parts:
            pattern = part.child("Pattern")
            r.field_into(pattern, "Mounting", "integer")
            r.field_into(pattern, "Pattern_CategoryName", "text")
            r.field_into(pattern, "Pattern_CategoryIndex", "integer")
            read_category_types(r, pattern, 'Pattern_CategoryTypes')
            read_possible_names(r, pattern)
            r.field_into(part, "Manufacturer", "text")
            r.field_into(part, "Component_CategoryName", "text")
            r.field_into(part, "Component_CategoryIndex", "integer")
            read_category_types(r, part, 'Component_CategoryTypes')
    if r.header.version >= 33:
        for page in schematic.child("Pages").children("Page"):
            r.field_into(page, "PageHiddenId", "integer")
        for part in parts:
            r.field_into(part, "PageHiddenId", "integer")
    else:
        # The older format component array leaves this identity zero, as does
        # its page array. Neither persistent field occurs in the older wire.
        for part in parts:
            r.add_into(part, 'PageHiddenId', 0)


def loads(data, *, source=None, allow_partial=False, ansi_encoding="cp1252", component_limit=None, context=None) -> Document:
    """Decode a binary buffer directly into our editable document model."""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError("DCH input must be bytes, bytearray or memoryview")
    data = bytes(data)
    from ..import_context import (resolve_import_context, modernize_font_settings)
    context = resolve_import_context(context)
    r = Reader(data, source=source, ansi_encoding=ansi_encoding)
    r.retain_source = context.retain_source
    doc = Document(representation='schematic')
    doc._automatic_structure = False
    doc.metadata.update(source_format="dch", source_path=source,
                        source_version=r.header.version, source_signature=r.header.signature,
                        source_string_encoding="utf-16-be" if r.header.unicode_text else ansi_encoding,
                        source_sha256=hashlib.sha256(data).hexdigest(), minimum_version=MIN_VERSION)
    schematic, count = _preamble(r, doc)
    doc.metadata["declared_component_count"] = count
    components = schematic.add("Components")
    if component_limit is not None and (not isinstance(component_limit, int) or component_limit < 0):
        raise ValueError("component_limit must be a nonnegative integer or None")
    for _ in range(min(count, component_limit) if component_limit is not None else count):
        part = _component_head(r, components)
        shape_count = _component_pins(r, part)
        _component_shapes(r, part, count=shape_count)
        pattern, pad_count = _component_pattern(r, part)
        _pattern_pads(r, pattern, count=pad_count)
        _pattern_graphics(r, pattern)
        _pattern_model(r, pattern)
        part.source = SourceSpan("dch", part.source.start, r.pos, r.source)
        part.annotations["incomplete"] = "later component extensions and ASC projection remain"
    if len(components.children()) == count:
        _page_connectors(r, schematic)
        _schematic_graphics(r, schematic)
        _nets(r, schematic)
        _buses_and_groups(r, schematic)
        _page_layouts(r, schematic)
        _tables(r, schematic)
        _settings(r, schematic)
        _extensions_to_33(r, schematic)
        if r.header.version >= 34:
            from .cache import (read_cache)
            read_cache(r, schematic)
        from .extensions import (read_common_extensions)
        from .modern import (read_drawing_extensions)
        from .tail import (read_project_extensions)
        from .recent import (read_recent_extensions)
        from .compat import (apply_version_defaults, restore_legacy_dimensions, recenter_legacy_symbols)
        read_common_extensions(r, schematic, doc)
        read_drawing_extensions(r, schematic)
        read_project_extensions(r, schematic)
        read_recent_extensions(r, schematic)
        apply_version_defaults(r.header.version, schematic)
        from .labels import (upgrade_global_labels)
        upgrade_global_labels(r.header.version, schematic)
        from .legacy_drawings import (expand_pattern_drawings, expand_symbol_drawings)
        expand_symbol_drawings(r.header.version, schematic)
        expand_pattern_drawings(r.header.version, schematic)
        from ...model.drawing_data import (normalize_drawings)
        normalize_drawings(schematic)
        from ..pictures import (upgrade_legacy_pictures)
        upgrade_legacy_pictures(r.header.version,schematic)
        modernize_font_settings(schematic, context)
        from .labels import (upgrade_instance_labels)
        upgrade_instance_labels(r.header.version, schematic,
            font_size=schematic.one('Settings').scalar('PartFontSize'),
            font_name=context.font_name, text_layout=context.layout)
        restore_legacy_dimensions(r.header.version, schematic)
        recenter_legacy_symbols(r.header.version, schematic)
        from ...model.cache import (upgrade_legacy_cache)
        upgrade_legacy_cache(schematic,version=r.header.version)
        from .compat import (complete_properties)
        complete_properties(schematic)
    doc.metadata["parsed_component_count"] = len(components.children())
    doc.metadata["parsed_bytes"] = r.pos
    doc.metadata["binary_consumed"] = r.pos == len(data)
    doc.metadata['binary_schema_complete'] = doc.metadata['binary_consumed']
    doc.metadata['export_equivalence_verified'] = False
    doc.complete = doc.metadata['binary_schema_complete']
    doc.metadata["unparsed_span"] = SourceSpan("dch", r.pos, len(data), source)
    if doc.complete:
        # Old construction-stage markers describe unfinished record prefixes.
        # EOF establishes complete typed wire data. Export equivalence is a
        # separate property of each destination adapter and its chosen context.
        for node in doc.root._record_walk(include_self=True):
            if node._annotations:
                node._annotations.pop('incomplete', None)
                if not node._annotations:
                    node._annotations = None
    else:
        doc.diagnostics.append(f'DCH decoding stops at byte {r.pos:#x}; later records remain')
    from ...model.refs import (bind_schematic_references)
    if doc.complete:
        from ...model.user_fields import (modernize_user_field_names)
        modernize_user_field_names(schematic)
        from ....common.cell_text import (modernize_cell_text)
        modernize_cell_text(schematic, paths=('Tables/Table/Cells/Cell', 'Pages/Page/TitleBlocks/TitleBlock/Contents/Content'))
    bind_schematic_references(doc, clamp_segments=True)
    if doc.metadata['binary_consumed']:
        from ...model.symbol_text import (refresh_symbol_text)
        refresh_symbol_text(doc)
        from .labels import (discard_legacy_label_slots)
        discard_legacy_label_slots(schematic)
        from ...editing.route_normalization import (normalize_imported_routes)
        normalize_imported_routes(doc)
        from ...model.refs import (unresolved_connectivity)
        if not unresolved_connectivity(doc) or schematic.scalar('HidePower') is False:
            from ...model.wire_visibility import (update_wire_visibility)
            update_wire_visibility(schematic)
        else:
            doc.diagnostics.append('Power-wire visibility deferred: unresolved attachment references')
    # Construction and version upgrades establish the loaded baseline. User
    # edits made after this point should be distinguishable from source data.
    doc.root._mark_loaded()
    if not context.retain_source:
        from ....common.source_details import discard_source
        discard_source(doc.root)
    if not allow_partial and not doc.complete:
        raise IncompleteDocumentError(doc.diagnostics[0])
    doc._automatic_structure = True
    return doc


def read(path, *, allow_partial=False, ansi_encoding="cp1252", component_limit=None, context=None) -> Document:
    """Read a file using the same decoder as the in-memory API."""
    path = Path(path)
    return loads(path.read_bytes(), source=str(path), allow_partial=allow_partial,
                 ansi_encoding=ansi_encoding, component_limit=component_limit, context=context)
