"""Small owned record constructors for imports and programmatic data work.

Starting values are declared authoring defaults. Geometry, connectivity and
display choices imported from a public format replace them explicitly.
"""
from .pads import (empty_pad)
from ...common.model import (Element)
from ...common import symbol_objects
from .new import (fields)
from .definitions import (PART, PIN,
                          SHEET_SHAPE, NET, NET_LINE, BUS_LINE)


def new_net(name=''):
    """Create an empty electrical net with standard schematic authoring choices."""
    net = Element('Net', name)
    fields(net, Number=0, Enabled=True, UniteByName=False, ConnectPinByName=False,
           Locked=False, ActiveLine=-1, ActivePoint=-1, Width=-1, Clearance=-1,
           NetClass=0, CustomColor=False, WireColor=0, Global=False, HiddenId=0)
    net.add('Parts')
    net.add('Lines')
    return net.bind_schema(NET)


def new_wire(*, bus=False):
    """Create wire data with unassigned connections; no geometry is calculated."""
    line = Element('Line')
    fields(line, Number=0, Page=0, Region=0, Selected=False, Group=-1,
           ConnectMode1=0 if bus else 4, ConnectMode2=0 if bus else 4, Connect1=-1, Connect2=-1,
           ConnectL1=-1, ConnectL2=-1, ConnectB1=-1, ConnectB2=-1)
    fields(line, **{'BusNumber' if bus else 'NetNumber': -1})
    if not bus:
        fields(line, Hidden=False, CanUnhide=False, Arrows=0)
    line.add('Points')
    return line.bind_schema(BUS_LINE if bus else NET_LINE)


def new_symbol_shape(index=0):
    return symbol_objects.new_drawing(index)


def new_schematic_shape(index=0):
    """Create a sheet drawing with editable text, image and line properties."""
    shape = new_symbol_shape(index)
    for name in ('ShowPart', 'MarkingGenerated'):
        shape.one(name).detach()
    fields(shape, Selected=False, Color=0, BrushColor=0, Page=0, BitmapIndex=-1,
           RelatedNet=-1, RelatedBus=-1, Picture_Width=0, Picture_Height=0,
           Picture_Transparent=0, Picture_File='', Picture_File_Variable='',
           Picture_Proportions=False, PictureFlipped=False)
    return shape.bind_schema(SHEET_SHAPE)


def new_pattern_shape(index=0, *, kind=0):
    from ...common.footprint_objects import new_pattern_drawing
    shape = new_pattern_drawing(index, kind=kind)
    shape.one('PadId').annotations['asc_omit'] = 'not present in ASC'
    return shape


def new_pattern(name=''):
    from ...common.footprint_objects import new_pattern as new_definition
    pattern = new_definition(name)
    pads, shapes, holes = (pattern.one(name) for name in ('Pads', 'Shapes', 'Holes'))
    for index in range(2):
        pads.append(empty_pad(index))
        shapes.append(new_pattern_shape(index))
        holes.add('Hole', False, False, 0, 0, 0, 0, -1)
    return pattern


def new_pin(index=0, *, placed=True):
    pin = symbol_objects.new_pin(index)
    if placed:
        fields(pin, NetNumber=-1, FConnect=False, Hidden=False, NoConnect=False,
               NetName='', SignalDelay=0)
        return pin.bind_schema(PIN)
    return pin


def new_symbol(name='', reference='', *, placed=True):
    if not placed:
        return symbol_objects.new_symbol(name, reference)
    part = symbol_objects.symbol_data(name, reference)
    supplier = part.one('Suppliers')
    fields(part, Selected=False, BaseName=name, BaseRefDes=reference, X=0, Y=0, Page=0,
           Group=-1, Number=0, PartNumber=0,
           PartDescriptor='', AllowParts=True, PartString='', HiddenId=0,
           Locked=False, Angle=0, LibPath='', LibPath_Variable='', Datasheet='',
           HorzFlip=False, VertFlip=False, ShowOrigin=False, PageHiddenId=0,
           CustomMarkingFont=False, MarkingFontSize=6, MarkingFontAll=False)
    for key in ('RefDes', 'Name'):
        part.add('Show'+key, 0, 0, 0, 0, 0, 0, 0, 0)
    for key in ('Value', 'Manufacturer', 'Datasheet'):
        part.add('Show'+key, 0, 0, 0, 0, 0, 0, 0)
    supplier.add('Prices').annotations['asc_omit'] = 'not present in ASC'
    supplier.add('MainSupplier', False)
    part.append(new_pattern())
    return part.bind_schema(PART)
