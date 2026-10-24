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

_OLD_TEXT_ALIGNMENT = {0: 1, 1: 2, 2: 5, 3: 7, 5: 3}


class Reader(Cursor):
    """Populate our document elements from named wire fields."""

    def argument(self, kind: str) -> Value:
        start = self.pos
        value = {"integer": self.integer, "number": self.number,
                 "boolean": self.boolean, "text": self.text, "color": self.color}[kind]()
        span = SourceSpan("dch", start, self.pos, self.source)
        value_kind = {'text': 'string', 'boolean': 'boolean'}.get(kind, 'number')
        return Value(value, value_kind, source=span)

    def record(self, parent: Element, name: str, *kinds: str) -> Element:
        """Read a public tuple, retaining provenance for every argument."""
        start = self.pos
        values = tuple(self.argument(kind) for kind in kinds)
        node = parent.append(Element(name, *values, source=SourceSpan('dch', start, self.pos, self.source)))
        node.annotations['source_version'] = self.header.version
        return node

    def field(self, parent: Element, name: str, kind: str, *, replace=False) -> Element:
        value = self.argument(kind)
        span = value.source
        node = parent.child(name) if replace else None
        if node is None:
            node = parent.append(Element(name, value, source=span))
        else:
            node.set_values(value)
            node.source = span
        node.annotations["source_version"] = self.header.version
        return node

    def fields(self, parent, layout, *, replace=False):
        """Read an ordered sequence of (public field name, wire type) pairs."""
        for name, kind in layout:
            self.field(parent, name, kind, replace=replace)
        return parent


def _preamble(r: Reader, doc: Document) -> tuple[Element, int]:
    doc.root.add("Source", "DipTrace-Schematic", 46)
    # Units are a separate format export setting; do not invent a value here.
    for kind, name in [("number", "Scale"), ("integer", "Xpos"), ("integer", "Ypos")]:
        node = r.field(doc.root, name, kind)
        if name == "Scale":
            stored = node.values[0]
            factor = min(Decimal(1000), max(Decimal('0.01'), stored))
            sign, digits, exponent = factor.as_tuple()
            percent = Decimal((sign, digits, exponent+2))
            node.set_argument(0, Value(percent, 'number', '%', source=node.arguments[0].source))
    schematic = doc.root.add("Schematic")
    r.field(schematic, "PictureCount", "integer")
    pages = schematic.add("Pages")
    for _ in range(r.count("pages")):
        start = r.pos
        page = pages.add("Page", r.argument('text'))
        page.source = SourceSpan("dch", start, r.pos, r.source)

        # The prefix repeats PageType; the later page layout is authoritative.
        r.integer()
        # Persistent page identity arrives in the schema-33 extension.
        if r.header.version <= 32:
            page.add("PageHiddenId", 0).annotations["default_for_version"] = r.header.version
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
        r.field(schematic, name, kind)
    classes = schematic.add("NetClasses")
    for _ in range(r.count("net classes")):
        node = classes.add("NetClass", r.argument('text'), r.argument('integer'), r.argument('number'), r.argument('number'), r.argument('integer'))
        node.annotations["incomplete"] = "remaining class settings occur later in the file"
    return schematic, r.count("components")


def _component_head(r: Reader, components: Element) -> Element:
    start = r.pos
    part = components.add("Part")
    r.fields(part, COMPONENT_PLACEMENT)
    name, ref, value, base_ref, base_name = [r.argument('text') for _ in range(5)]
    part.set_values(name, ref)
    for key, val in (("Value", value), ("BaseName", base_name), ("BaseRefDes", base_ref)):
        part.add(key, val)
    for name in ("ShowText", "TextAlign"):
        r.field(part, name, "integer")
    r.field(part, "LockProperties", "boolean")
    for kind, name in [("integer", "PartNumber"), ("integer", "PartType"),
                       ("text", "PartName"), ("text", "PartDescriptor"), ("boolean", "AllowParts"),
                       ("integer", "ShowText2"), ("integer", "TextAlign2"), ("integer", "ShowNumbers")]:
        r.field(part, name, kind)
    for name in ("TextPosX", "TextPosY", "TextPosX2", "TextPosY2"):
        r.field(part, name, "number")
    r.field(part, "PartString", "text")
    r.field(part, "HiddenId", "integer")
    fields = part.add("UserFields")
    for _ in range(r.count("component user fields")):
        fields.add("UserField", r.argument('text'), r.argument('text'), r.argument('integer'))
    for name in ("FieldIndex1", "FieldIndex2"):
        r.field(part, name, "integer")
    r.field(part, "Locked", "boolean")
    angle = r.field(part, "Angle", "number")
    if not r.header.angles_in_degrees:
        radians = angle.values[0]
        angle.set_argument(0, Decimal(str(round(float(radians) * 180 / math.pi, 4))))
    for kind, name in [("text", "LibPath"), ("integer", "ModelType")]:
        r.field(part, name, kind)
    part.source = SourceSpan("dch", start, r.pos, r.source)
    part.annotations["incomplete"] = "component body follows this decoded scalar prefix"
    return part


def _component_pins(r: Reader, part: Element):
    """format gates for this prefix all precede minimum schema 29."""
    model_body = part.add("ModelBody")
    for _ in range(r.count("model text lines")):
        model_body.add("Line", r.argument('text'))
    r.field(part, "ModelString", "text")
    r.field(part, "Datasheet", "text")
    r.field(part, "HorzFlip", "boolean")
    r.field(part, "VertFlip", "boolean")
    pins = part.add("Pins")
    for index in range(r.count("pins")):
        start = r.pos
        pin = pins.add("Pin", index)
        r.field(pin, "Enabled", "boolean")
        for name in ("Type", "Orientation", "Number", "NetNumber"):
            r.field(pin, name, "integer")
        pin.set_values(index, r.argument('number'), r.argument('number'))
        r.field(pin, "Length", "number")
        for name in ("Name", "StringNumber"):
            r.field(pin, name, "text")
        for name in ("FConnect", "ShowName"):
            r.field(pin, name, "boolean")
        for name in ("PinNumXShift", "PinNumYShift", "PinNameXShift", "PinNameYShift"):
            r.field(pin, name, "number")
        r.field(pin, "ElectricType", "integer")
        for name in ("Hidden", "Locked"):
            r.field(pin, name, "boolean")
        r.field(pin, "ModelSig", "text")
        r.field(pin, "NoConnect", "boolean")
        r.fields(pin, PIN_FONT)
        pin.source = SourceSpan("dch", start, r.pos, r.source)
    part.annotations["declared_shape_count"] = r.count("component shapes")
    part.annotations["incomplete"] = "component shapes and following fields are not decoded"


def _component_shapes(r: Reader, part: Element, *, placed=True):
    shapes = part.add("Shapes")
    for index in range(part.annotations["declared_shape_count"]):
        start = r.pos
        shape = shapes.add("Shape", index)
        if not placed:
            # Cached symbol drawings never serialize the placed-only flag.
            shape.add('ShowPart', False).annotations['default_for_version'] = r.header.version
        r.field(shape, "Enabled", "boolean")
        r.field(shape, "Orientation", "integer")
        kind = r.field(shape, "Type", "integer")
        # Only the placed-symbol reader recognizes the old marking tag. Cached
        # symbols use the same field layout but keep their ordinary type value.
        generated = placed and kind.values[0] == 700
        if generated:
            kind.set_argument(0, 10)
        r.field(shape, "FontSize", "integer")
        r.field(shape, "FontColor", "color")
        r.field(shape, "FontType", "integer")
        r.field(shape, "FontName", "text")
        r.field(shape, "Name", "text")
        shape.add('TextLine').add('pt', shape.child('Name').arguments[0])
        r.field(shape, "PenWidth", "number")
        # The >=40 format stores the editable geometry. format export also
        # projects historical text bounds, which require its layout rules.
        points = shape.add("Points_New" if r.header.version >= 40 else "Points")
        for _ in range(r.count("shape points")):
            points.add("pt", r.argument('number'), r.argument('number'))
        r.field(shape, "Locked", "boolean")
        r.field(shape, "VectorFont", "boolean")
        r.field(shape, "FontWidth", "number")
        r.field(shape, "FontScale", "number")
        shape.add("MarkingGenerated", generated)
        shape.source = SourceSpan("dch", start, r.pos, r.source)
        shape.annotations["incomplete"] = "format text/layout projection and derived ASC fields remain to be mapped"
    part.annotations["incomplete"] = "component suffix after its shape array remains to be decoded"


def _component_pattern(r: Reader, part: Element):
    """Component pattern."""
    start = r.pos
    pattern = part.add("Pattern")
    connections = pattern.add("InternalConnections")
    for _ in range(r.count("footprint internal connections")):
        connections.add("IntCon", r.argument('integer'), r.argument('integer'))
    _pattern_parameters(r, pattern)
    for name in ("Origin_X", "Origin_Y"):
        r.field(part, name, "number")
    r.field(part, "ShowOrigin", "boolean")
    fields = pattern.add("UserFields")
    for _ in range(r.count("footprint user fields")):
        fields.add("UserField", r.argument('text'), r.argument('text'), r.argument('integer'))
    points = pattern.add("PadPoints")
    for _ in range(r.count("footprint default pad points")):
        points.add("pt", r.argument('number'), r.argument('number'))
    pattern.source = SourceSpan("dch", start, r.pos, r.source)
    pattern.annotations["declared_pad_count"] = r.count("footprint pads")
    pattern.annotations["incomplete"] = "footprint pads and later settings remain to be decoded"
    part.annotations["incomplete"] = "component footprint body and later fields remain to be decoded"
    return pattern


def _pattern_parameters(r: Reader, pattern: Element):
    """Shared ordered footprint fields for placed parts and cache definitions."""
    r.field(pattern, "Type", "integer")
    for index in range(1, 5):
        r.field(pattern, f"VariableParameter{index}", "boolean")
    for name in ("Number1", "Number2"):
        r.field(pattern, name, "integer")
    for name in ("Spacing1", "Spacing2"):
        r.field(pattern, name, "number")
    r.field(pattern, "VariableParameter5", "boolean")
    r.field(pattern, "Spacing3", "number")
    r.field(pattern, "LockProperties", "boolean")
    r.field(pattern, "PatternOrientation", "integer")
    for name in ("Width", "Height", "PadWidth", "PadHeight"):
        r.field(pattern, name, "number")
    r.field(pattern, "PadShape", "integer")
    r.field(pattern, "SurfacePad", "boolean")
    for name in ("PadHole", "PadHoleH"):
        r.field(pattern, name, "number")
    r.field(pattern, "PadHoleType", "integer")
    pattern.set_values(r.argument('text'))
    for name in ("OriginX", "OriginY"):
        r.field(pattern, name, "number")


def _pattern_pads(r: Reader, pattern: Element, *, omit_reserved=True):
    """Extended pad properties occur later in the component. These nodes remain
    incomplete until those extensions and the format compatibility projection
    have been applied.
    """
    pads = pattern.add("Pads")
    for index in range(pattern.annotations["declared_pad_count"]):
        start = r.pos
        inverted = r.argument('boolean')
        pad = pads.add("Pad", index)
        number = r.argument('integer')
        x, y = r.argument('number'), r.argument('number')
        name, detail = r.argument('text'), r.argument('text')
        pad.set_values(index, name, detail, x, y)
        if index in (0, pattern.annotations["declared_pad_count"]-1):
            pad.annotations['reserved'] = True
        if omit_reserved and pad.annotations.get('reserved'):

            # Keep the two additional records available for investigation.
            pad.annotations["asc_omit"] = "reserved pad record outside the format export range"
        pad.add("Number_New", number)
        pad.add("PadAngle", Decimal(str(math.pi/2)) if inverted.value else Decimal(0))
        for name in ("PadWidth_New", "PadHeight_New", "PadHole", "PadHoleH"):
            r.field(pad, name, "number")
        r.field(pad, "PadHoleType", "integer")
        r.field(pad, "SurfacePad", "boolean")
        r.field(pad, "PadShape_New", "integer")
        standard = r.boolean()
        pad.add("Standard", standard)
        point_count = r.count("pad polygon points")
        if point_count:
            points = pad.add("PadPoints_New")
            for _ in range(point_count):
                r.record(points, 'pt', 'number', 'number')
        r.field(pad, "Locked", "boolean")
        r.field(pad, "Sided", "boolean")
        # Schema 29 introduced these four booleans. format upgrades each to
        # state 2 (disabled) or 0 (inherited); later records can override them.
        for name in ("DisableTopMask", "DisableBottomMask", "DisableTopPaste", "DisableBottomPaste"):
            disabled = r.boolean()
            pad.add(name, 2 if disabled else 0)
        for name in ("CustomSwell_New", "CustomShrink_New"):
            r.field(pad, name, "number")
        pad.source = SourceSpan("dch", start, r.pos, r.source)
        pad.annotations["incomplete"] = "extended pad fields and compatibility projection remain"
    pattern.annotations["incomplete"] = "footprint shapes and later fields remain to be decoded"


def _pattern_graphics(r: Reader, pattern: Element):
    """Graphics use our nested shape representation. ASC flattens footprint
    shape properties into successive sibling records; that projection is a
    writer concern, not a reason to duplicate its old memory structures here.
    """
    shapes = pattern.add("Shapes")
    for index in range(r.count("footprint shapes")):
        start = r.pos
        shape = shapes.add("Shape", index)
        r.field(shape, "Type", "integer")
        if r.header.version < 40:
            r.record(stored_data(shape), 'CompatibilityGeometry', *('number',)*6)
        else:
            for _ in range(6):
                r.number()  # Superseded by the physical-coordinate extension.
        r.field(shape, "Locked", "boolean")
        r.field(shape, "Layer", "integer")
        shape.add("TextLine").add("pt", r.argument('text'))
        r.field(shape, "FontName", "text")
        r.field(shape, "VectorFont", "boolean")
        # The flat ASC tuple does not label these arguments. Public DCHXML

        r.field(shape, "FontSize", "integer")
        for name in ("FontScale", "FontWidth"):
            r.field(shape, name, "number")
        if r.header.version < 40:
            r.field(stored_data(shape), 'TextOrientation', 'integer')
        else:
            r.integer()  # Current TextAngle arrives in the extension.
        r.field(shape, 'TextShow', 'integer')
        r.field(shape, "Width", "number")
        count = r.count("footprint shape points")
        points = shape.add("Points_New")
        for _ in range(count):
            r.record(points, 'pt', 'number', 'number')
        shape.source = SourceSpan("dch", start, r.pos, r.source)
        shape.annotations["incomplete"] = "extended geometry and legacy ASC projection remain"
    holes = pattern.add("Holes")
    for _ in range(r.count("footprint holes")):
        start = r.pos
        first = r.argument('boolean')


        x, y, diameter, hole_diameter = (r.argument('number') for _ in range(4))
        second = r.argument('boolean')
        hole = holes.add("Hole", first, second, x, y, diameter, hole_diameter)
        hole.source = SourceSpan("dch", start, r.pos, r.source)
        hole.annotations["incomplete"] = "hole group is stored in the later extension"
    dimensions = pattern.add("Dimensions")
    for index in range(r.count("footprint dimensions")):
        start = r.pos
        dimension = dimensions.add("Dimension", index)
        for name in ("Enabled", "Locked"):
            r.field(dimension, name, "boolean")
        for name in ("Type", "Connected1", "Object1", "SubObject1", "Point1",
                     "Connected2", "Object2", "SubObject2", "Point2", "Layer"):
            r.field(dimension, name, "integer")
        for name in ("X1", "Y1", "X2", "Y2", "XD", "YD", "ArrowSize"):
            r.field(dimension, name, "number")
        r.field(dimension, "Units", "integer")
        r.field(dimension, "VectorFont", "boolean")
        r.field(dimension, "FontName", "text")
        r.field(dimension, "FontSize", "integer")
        for name in ("FontScale", "FontWidth"):
            r.field(dimension, name, "number")
        r.field(dimension, "ShowUnits", "boolean")
        r.field(dimension, "Angle", "number")
        for name in ("ExternalRadius", "PointerMode"):
            r.field(dimension, name, "integer")
        r.field(dimension, "PointerText", "text")
        dimension.source = SourceSpan("dch", start, r.pos, r.source)
        dimension.annotations["incomplete"] = "dimension group is stored in the later extension"


def _pattern_model(r: Reader, pattern: Element):
    model = pattern.add("Model3D")
    r.field(model, "Model3DFile", "text")
    # Public XML terminology, linked to the DCH reader and ASC tuple by the

    # the ASC tuple orders Rotate before Offset. Keep named data in our tree.
    for name in ('Offset', 'Rotate', 'Zoom'):
        vector = model.add(name)
        for axis in ('X', 'Y', 'Z'):
            r.field(vector, axis, 'number')
    r.field(model, 'Mirror', 'boolean')
    r.field(model, 'NoSearch', 'boolean')
    model.annotations["incomplete"] = "later 3D settings and ASC projection remain"
    pattern.annotations["incomplete"] = "later footprint extensions and ASC projection remain"


def _page_connectors(r: Reader, schematic: Element):
    connectors = schematic.add("PageConnectors")
    for _ in range(r.count("page connectors")):
        start = r.pos
        node = connectors.add("PageConnector")
        for name in ("Enabled", "Selected", "Connected"):
            r.field(node, name, "boolean")
        x, y = r.argument('number'), r.argument('number')
        for name in ("Page", "BusNumber", "Number", "Region", "Group"):
            r.field(node, name, "integer")
        node.set_values(r.argument('text'), x, y)
        r.field(node, "Locked", "boolean")
        node.source = SourceSpan("dch", start, r.pos, r.source)


def _schematic_graphics(r: Reader, schematic: Element):
    shapes = schematic.add("Shapes")
    for index in range(r.count("schematic shapes")):
        start = r.pos
        shape = shapes.add("Shape", index)
        for name in ("Enabled", "Selected"):
            r.field(shape, name, "boolean")
        r.field(stored_data(shape), 'Orientation', 'integer')
        for name in ("Type", "FontSize"):
            r.field(shape, name, "integer")
        for name in ("FontColor", "Color", "BrushColor"):
            r.field(shape, name, "color")
        for name in ("FontType", "Page", "Group"):
            r.field(shape, name, "integer")
        r.field(shape, "PenWidth", "number")
        r.field(shape, "FontName", "text")
        shape.add("TextLine").add("pt", r.argument('text'))
        bitmap = r.field(shape, "BitmapIndex", "integer")

        # Earlier pictures can still need their external resource table. Later
        # file-backed drawings do not use this transient bitmap-cache index.
        if r.header.version>=42 or shape.scalar('Type')!=11:
            bitmap.set_argument(0, -1)
        points = shape.add("Points_New" if r.header.version >= 40 else "Points")
        for _ in range(r.count("schematic shape points")):
            points.add("pt", r.argument('number'), r.argument('number'))
        for name in ("RelatedNet", "RelatedBus"):
            r.field(shape, name, "integer")
        r.field(shape, "Locked", "boolean")
        r.field(shape, "VectorFont", "boolean")
        for name in ("FontWidth", "FontScale"):
            r.field(shape, name, "number")
        shape.source = SourceSpan("dch", start, r.pos, r.source)
        shape.annotations["incomplete"] = "later drawing fields and format layout projection remain"


def _nets(r: Reader, schematic: Element):
    nets = schematic.add("Nets")
    for _ in range(r.count("nets")):
        start = r.pos
        net = nets.add("Net")
        r.field(net, "Enabled", "boolean")
        r.boolean()  # Obsolete net selection slot; not a current property.
        for name in ("UniteByName", "ConnectPinByName"):
            r.field(net, name, "boolean")
        for name in ("ActiveLine", "ActivePoint", "Number"):
            r.field(net, name, "integer")
        r.integer()  # Discarded compatibility slot.
        net.set_values(r.argument('text'))
        for name in ("Width", "Clearance"):
            r.field(net, name, "number")
        r.field(net, "NetClass", "integer")
        r.field(net, "Global", "boolean")
        parts = net.add("Parts")
        for _ in range(r.count("net pin references")):
            r.record(parts, 'pt', 'integer', 'integer')
        lines = net.add("Lines")
        for _ in range(r.count("net lines")):
            line_start = r.pos
            line = lines.add("Line")
            for name in ("Connect1", "Connect2", "ConnectL1", "ConnectL2", "ConnectB1", "ConnectB2",
                         "Page", "ConnectMode1", "ConnectMode2", "NetNumber", "Region", "Number"):
                r.field(line, name, "integer")
            r.field(line, "Hidden", "boolean")
            points = line.add("Points")
            for _ in range(r.count("wire points")):
                r.record(points, 'pt', 'number', 'number', 'integer')
            r.field(line, "Selected", "boolean")
            r.field(line, "Group", "integer")
            r.field(line, "CanUnhide", "boolean")
            r.field(line, "Arrows", "integer")
            line.source = SourceSpan("dch", line_start, r.pos, r.source)
        for name in ("Locked", "CustomColor"):
            r.field(net, name, "boolean")
        r.field(net, "WireColor", "color")
        net.source = SourceSpan("dch", start, r.pos, r.source)
        net.annotations["incomplete"] = "later net extension fields remain"


def _buses_and_groups(r: Reader, schematic: Element):
    """Buses and groups."""
    buses = schematic.add("Buses")
    for _ in range(r.count("buses")):
        start = r.pos
        bus = buses.add("Bus")
        r.field(bus, "Enabled", "boolean")
        r.boolean()  # Obsolete bus selection slot; not a current property.
        for name in ("ActiveLine", "ActivePoint", "Number", "Region"):
            r.field(bus, name, "integer")
        r.integer()  # Discarded compatibility slot.
        bus.set_values(r.argument('text'))
        nets = bus.add("Nets")
        for _ in range(r.count("bus nets")):
            nets.add("pt", r.argument('integer'))
        lines = bus.add("Lines")
        for _ in range(r.count("bus lines")):
            line_start = r.pos
            line = lines.add("Line")
            for name in ("Connect1", "Connect2", "ConnectL1", "ConnectL2", "ConnectB1", "ConnectB2",
                         "Page", "ConnectMode1", "ConnectMode2", "BusNumber", "Region", "Number"):
                r.field(line, name, "integer")
            points = line.add("Points")
            for _ in range(r.count("bus wire points")):
                points.add("pt", r.argument('number'), r.argument('number'), r.argument('integer'))
            r.field(line, "Selected", "boolean")
            r.field(line, "Group", "integer")
            line.source = SourceSpan("dch", line_start, r.pos, r.source)
        r.field(bus, "Locked", "boolean")
        numbers = bus.add("Numbers")
        for _ in range(r.count("bus numbers")):
            numbers.add("pt", r.argument('integer'))
        bus.source = SourceSpan("dch", start, r.pos, r.source)
    groups = schematic.add("Groups")
    for _ in range(r.count("groups")):
        start = r.pos
        group = groups.add("Group")
        for name in ("Enabled", "Selected"):
            r.field(group, name, "boolean")
        group.set_values(r.argument('integer'), r.argument('number'), r.argument('number'))
        group.source = SourceSpan("dch", start, r.pos, r.source)


def _title_grid(r: Reader, parent: Element, index: int):
    """Cell placement, shared text styles and grid borders are explicit editable
    elements. No format arrays or memory offsets become document structures.
    """
    start = r.pos
    grid = parent.add("TitleBlock", index, r.argument('text'))
    r.field(grid, "Width", "number")
    r.field(grid, "Height", "number")
    columns, rows = r.count("title columns"), r.count("title rows")
    widths = grid.add("ColWidths")
    for _ in range(columns):
        widths.add("pt", r.argument('number'))
    heights = grid.add("RowHeights")
    for _ in range(rows):
        heights.add("pt", r.argument('number'))
    if columns * rows > (len(r.data) - r.pos) // 7:
        raise DchError(f"title grid dimensions exceed remaining data at byte {r.pos:#x}")
    cells = grid.add("Cells")
    for column in range(columns):
        for row in range(rows):
            cell = cells.add("Cell", column, row, r.argument('integer'))
            cell.add("Edges", *(r.argument('boolean') for _ in range(4)))
    contents = grid.add("Contents")
    for index in range(r.count("title cell contents")):
        cell = contents.add("Content", index)
        r.field(cell, "FOrientation", "boolean")
        for name in ("FontSize", "FontType", "Align"):
            r.field(cell, name, "integer")
        r.field(cell, "FontColor", "color")
        r.field(cell, "Text", "text")
        r.field(cell, "FontName", "text")
        cell.add("Placement", *(r.argument('number') for _ in range(4)))
        r.field(cell, "VectorFont", "boolean")
        for name in ("FontWidth", "FontScale"):
            r.field(cell, name, "number")
    grid.source = SourceSpan("dch", start, r.pos, r.source)
    # ASC has no title-grid record; retain this source-only page content for
    # querying/editing and make the intentional projection omission visible.
    grid.annotations["asc_omit"] = "format schematic ASC does not emit page title grids"


def _page_layouts(r: Reader, schematic: Element):
    pages = schematic.child("Pages").children("Page")
    # The format loop uses the earlier page-array length; the repeated stored

    r.integer()  # Repeated framing count; the page array determines this loop.
    for page in pages:
        start = r.pos
        zones = page.add("Zones")
        for name in ("PageWidth", "PageHeight"):
            r.field(page, name, "number")
        for name in ("FLeft", "FTop", "FRight", "FBottom"):
            r.field(page, name, "number")
        titles = page.add("TitleBlocks")
        titles.annotations["asc_omit"] = "format schematic ASC does not emit page title grids"
        for index in range(6):
            _title_grid(r, titles, index)
        zones.set_values(r.argument('boolean'))
        for name in ("HorzZones", "VertZones", "ZoneStandard"):
            r.field(page, name, "integer")
        r.field(page, "ZoneFontName", "text")
        r.field(page, "ZoneFontSize", "integer")
        r.field(page, "ZoneBorder", "boolean")
        for name in ("HorzZoneBorder", "VertZoneBorder"):
            r.field(page, name, "number")
        for name in ("PageXPos", "PageyPos"):
            r.field(page, name, "integer")
        scale = r.field(page, "PageScale", "number")
        original = scale.values[0]
        scale.set_argument(0, min(Decimal(1000), max(Decimal('0.01'), original)))
        # The border-zone font width uses the public XML FontLineWidth name.
        r.field(page, 'FontLineWidth', 'number').annotations['asc_omit'] = 'zone font pen is not present in ASC'
        r.field(page, "PageType", "integer")
        page.annotations["layout_source"] = SourceSpan("dch", start, r.pos, r.source)


def _tables(r: Reader, schematic: Element):
    """Tables."""
    tables = schematic.add("Tables")
    for _ in range(r.count("tables")):
        start = r.pos
        table = tables.add("Table")
        for name in ("Enabled", "Selected"):
            r.field(table, name, "boolean")
        for name in ("Layer", "DefAlign", "DefFontSize", "Orientation", "Group", "Page"):
            r.field(table, name, "integer")
        r.field(table, "DefFontColor", "color")
        for name in ("DefCellWidth", "DefCellHeight", "X1", "Y1", "X2", "Y2"):
            r.field(table, name, "number")
        for name in ("DefFontName", "Name"):
            r.field(table, name, "text")
        columns = r.count("table columns")
        widths = table.add("ColWidths")
        for _ in range(columns):
            widths.add("pt", r.argument('number'))
        rows = r.count("table rows")
        heights = table.add("RowHeights")
        for _ in range(rows):
            heights.add("pt", r.argument('number'))
        # Every cell requires at least its boolean, three integers, color,
        # two strings, four numbers, a second boolean and two more numbers.
        if columns * rows > (len(r.data) - r.pos) // 42:
            raise DchError(f"table dimensions exceed remaining data at byte {r.pos:#x}")
        cells = table.add("Cells")
        for column in range(columns):
            for row in range(rows):
                cell_start = r.pos
                cell = cells.add("Cell")
                for kind, name in [("boolean", "FOrientation"), ("integer", "FontSize"),
                                   ("integer", "FontType"), ("integer", "Align"),
                                   ("color", "FontColor"), ("text", "Text"), ("text", "FontName")]:
                    r.field(cell, name, kind)
                cell.set_values(*(r.argument('number') for _ in range(4)))
                r.field(cell, "VectorFont", "boolean")
                for name in ("FontWidth", "FontScale"):
                    r.field(cell, name, "number")
                cell.source = SourceSpan("dch", cell_start, r.pos, r.source)
        for name in ("Locked", "DefVectorFont"):
            r.field(table, name, "boolean")
        for name in ("DefFontWidth", "DefFontScale"):
            r.field(table, name, "number")
        r.field(table, "HideBorder", "boolean")
        table.source = SourceSpan("dch", start, r.pos, r.source)
        table.annotations["incomplete"] = "later line-spacing settings and format cell-text projection remain"


def _settings(r: Reader, schematic: Element):
    """Settings."""
    settings = schematic.add("Settings")
    r.field(settings, "GridSize", "number")
    r.field(settings, "OriginEnabled", "boolean")
    r.field(settings, "clAxis", "color")
    for name in ("BusConnectionFont", "PinNumberFont"):
        r.field(settings, name, "integer")
    for name in ("GridEnabled", "DisplayTitles", "DisplaySheet", "BusConNetName", "BusConNetNumber",
                 "ShowPinNumbers", "HidePinNumbers", "BusConAbove", "BusConBelow"):
        r.field(settings, name, "boolean")
    for name in ("BusLineWidth", "WireLineWidth", "TableLineWidth", "TitlesLineWidth", "NodeSize"):
        r.field(settings, name, "number")
    for name in ("UnitsMM", "UnitsMIL", "UnitsINCH", "ERC_PinType", "ERC_NotConnected", "ERC_SinglePin", "ERC_Short"):
        r.field(settings, name, "boolean")
    for name in ("ERC_VCCTemplate", "ERC_GNDTemplate"):
        r.field(settings, name, "text")
    if r.header.version >= 30:
        r.field(settings, "ERC_PinSuperimpose", "boolean")
    else:
        settings.add("ERC_PinSuperimpose", True).annotations["default_for_version"] = r.header.version


def _extensions_to_33(r: Reader, schematic: Element):
    """Extensions to 33."""
    parts = schematic.child("Components").children("Part")
    if r.header.version >= 31:
        for part in parts:
            model = part.child("Pattern").child("Model3D")
            r.field(model, 'Units', 'integer')
            for pin in part.child("Pins").children("Pin"):
                r.field(pin, "NetName", "text")
    else:
        for part in parts:
            part.child('Pattern').child('Model3D').add('Units', -1).annotations['default_for_version'] = r.header.version
            for pin in part.child("Pins").children("Pin"):
                pin.add("NetName", "").annotations["default_for_version"] = r.header.version
    if r.header.version >= 32:
        for part in parts:
            pattern = part.child("Pattern")
            r.field(pattern, "Mounting", "integer")
            r.field(pattern, "Pattern_CategoryName", "text")
            r.field(pattern, "Pattern_CategoryIndex", "integer")
            count = r.count("footprint category types")
            types = pattern.add("Pattern_CategoryTypes", count)
            for _ in range(count):
                types.add("CategoryType", r.argument('text'), r.argument('text'), r.argument('integer'), r.argument('integer'))
            count = r.count("possible footprint names")
            names = pattern.add("PossibleNames", count)
            for _ in range(count):
                names.add("PossibleName", r.argument('text'))
            r.field(part, "Manufacturer", "text")
            r.field(part, "Component_CategoryName", "text")
            r.field(part, "Component_CategoryIndex", "integer")
            count = r.count("component category types")
            types = part.add("Component_CategoryTypes", count)
            for _ in range(count):
                types.add("CategoryType", r.argument('text'), r.argument('text'), r.argument('integer'), r.argument('integer'))
    if r.header.version >= 33:
        for page in schematic.child("Pages").children("Page"):
            r.field(page, "PageHiddenId", "integer")
        for part in parts:
            r.field(part, "PageHiddenId", "integer")
    else:
        # The older format component array leaves this identity zero, as does
        # its page array. Neither persistent field occurs in the older wire.
        for part in parts:
            part.add('PageHiddenId', 0).annotations['default_for_version'] = r.header.version


def loads(data, *, source=None, allow_partial=False, ansi_encoding="cp1252", component_limit=None, context=None) -> Document:
    """Decode a binary buffer directly into our editable document model."""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError("DCH input must be bytes, bytearray or memoryview")
    data = bytes(data)
    from ..import_context import (resolve_import_context, modernize_font_settings)
    context = resolve_import_context(context)
    r = Reader(data, source=source, ansi_encoding=ansi_encoding)
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
        _component_pins(r, part)
        _component_shapes(r, part)
        pattern = _component_pattern(r, part)
        _pattern_pads(r, pattern)
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
        for node in doc.root.walk(include_self=True):
            if node.annotations.pop('incomplete', None) is not None:
                node.annotations['requires_asc_projection'] = True
        doc.root.annotations['requires_asc_projection'] = True
    else:
        doc.diagnostics.append(f'DCH decoding stops at byte {r.pos:#x}; later records remain')
    from ...model.refs import (bind_schematic_references)
    if doc.complete:
        from ...model.user_fields import (modernize_user_field_names)
        modernize_user_field_names(schematic)
        from ...model.cell_text import (modernize_cell_text)
        modernize_cell_text(schematic)
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
    for node in doc.root.walk(include_self=True):
        node._dirty = False
        node._reordered = False
    if not allow_partial and not doc.complete:
        raise IncompleteDocumentError(doc.diagnostics[0])
    doc._automatic_structure = True
    return doc


def read(path, *, allow_partial=False, ansi_encoding="cp1252", component_limit=None, context=None) -> Document:
    """Read a file using the same decoder as the in-memory API."""
    path = Path(path)
    return loads(path.read_bytes(), source=str(path), allow_partial=allow_partial,
                 ansi_encoding=ansi_encoding, component_limit=component_limit, context=context)
