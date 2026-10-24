"""Small owned record constructors for imports and programmatic data work.

Starting values are declared authoring defaults. Geometry, connectivity and
display choices imported from a public format replace them explicitly.
"""
from .pads import (empty_pad)
from ...common.model import (Element)
from .new import (fields)
from .definitions import (PART, CACHED_PART, PIN, CACHED_PIN, PATTERN, SYMBOL_SHAPE,
                          SHEET_SHAPE, PATTERN_SHAPE, NET, NET_LINE, BUS_LINE)


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
    shape = Element('Shape', index)
    fields(shape, Enabled=True, Type=1, FontSize=6, FontColor=0, FontType=0,
           FontName='', PenWidth=.3, TextAngle=0, TextHorz=0, TextVert=0,
           TextAlign=0, LineSpacing=1.2, Group=-1, ShowPart=False, MarkingGenerated=False,
           Locked=False, VectorFont=True, FontWidth=-1, FontScale=1, FontMono=False)
    for name in ('TextLine', 'Points_New'):
        shape.add(name)
    return shape.bind_schema(SYMBOL_SHAPE)


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
    shape = Element('Shape', index)
    fields(shape, Type=kind, Locked=False, Layer=0, FontName='', VectorFont=True,
           FontSize=6, FontScale=1, FontWidth=-1, TextShow=0, Width=.3,
           TextAngle=0, TextHorz=0, TextVert=0, TextAlign=0, LineSpacing=1.2,
           AllLayers=False, Group=-1, FontMono=False)
    for name in ('TextLine', 'Points_New'):
        shape.add(name)
    pad_id = shape.add('PadId', -1)
    pad_id.annotations['asc_omit'] = 'not present in ASC'
    return shape.bind_schema(PATTERN_SHAPE)


def new_pattern(name=''):
    pattern = Element('Pattern', name)
    fields(pattern, Type=0, VariableParameter1=False, VariableParameter2=False,
           VariableParameter3=False, VariableParameter4=False, VariableParameter5=False,
           Number1=0, Number2=0, Spacing1=0, Spacing2=0, Spacing3=0, LockProperties=False,
           PatternOrientation=0, Width=0, Height=0, OriginCross=True, OriginCircle=True,
           OriginCommon=1, OriginCourtyard=0, Name_Description='', Name_Unique='',
           RecoveryCode='', RecoveryCode_Generator=True, RecoveryCode_Model=True,
           Pattern_Manufacturer='', PadCorner=0, PadShape_X=0, PadShape_Y=0,
           PadWidth=0, PadHeight=0, PadShape=0, SurfacePad=False, PadHole=0, PadHoleH=0,
           PadHoleType=0, TopMask_State=0, BotMask_State=0,
           TopPaste_State=0, BotPaste_State=0, CustomSwell_New=-1000, CustomShrink_New=-1000,
           PadMask_Percent=50, PadMask_EdgeGap=.9, PadMask_SegmentGap=.6,
           PadMask_SegmentSide=3, OriginX=0, OriginY=0, Mounting=-1,
           Pattern_CategoryName='', Pattern_CategoryIndex=-1)
    for key in ('InternalConnections', 'UserFields', 'PadPoints', 'Pattern_Groups',
                'PadMask_TopSegments', 'PadMask_BotSegments', 'Dimensions', 'PossibleNames',
                'Pattern_CategoryTypes'):
        pattern.add(key)
    pads = pattern.add('Pads')
    pads.append(empty_pad(0))
    pads.append(empty_pad(1))
    shapes = pattern.add('Shapes')
    for index in range(2):
        shapes.append(new_pattern_shape(index))
    holes = pattern.add('Holes')
    for _ in range(2):
        holes.add('Hole', False, False, 0, 0, 0, 0, -1)
    model = pattern.add('Model3D')
    fields(model, Model3DFile='', Model3DFile_Variable='', Mirror=False, NoSearch=False,
           Units=0, IPC_XOff=0, IPC_YOff=0, AutoHeight=0, AutoColor=0x4B4B4B,
           Type=0, KeepPins=False)
    for name in ('Offset', 'Rotate', 'Zoom'):
        fields(model.add(name), X=1 if name == 'Zoom' else 0, Y=1 if name == 'Zoom' else 0,
               Z=1 if name == 'Zoom' else 0)
    return pattern.bind_schema(PATTERN)


def new_pin(index=0, *, placed=True):
    pin = Element('Pin', index, 0, 0)
    fields(pin, Enabled=True, Type=0, Orientation=0, Number=-1, Length=3, Name='',
           StringNumber='', ShowName=True, PinNumXShift=0, PinNumYShift=0,
           PinNameXShift=0, PinNameYShift=0, ElectricType=0, Locked=False, ModelSig='',
           NameFontSize=6, NameFontWidth=-1, NameFontScale=1, Group=-1,
           PinNameRotate=0, PinNumRotate=0, NameFontMono=False)
    if placed:
        fields(pin, NetNumber=-1, FConnect=False, Hidden=False, NoConnect=False,
               NetName='', SignalDelay=0)
    return pin.bind_schema(PIN if placed else CACHED_PIN)


def new_symbol(name='', reference='', *, placed=True):
    part = Element('Part', name, reference)
    fields(part, Enabled=True, PartType=0, PartName='', ShowNumbers=0, Type=0,
           Number1=0, Number2=0, Width=0, Height=0, Value='', LockProperties=False,
           Origin_X=0, Origin_Y=0, ModelType=0, ModelString='', Manufacturer='',
           Component_CategoryName='', Component_CategoryIndex=-1)
    for key in ('Pins', 'Shapes', 'UserFields', 'ModelBody', 'Component_CategoryTypes'):
        part.add(key)
    supplier = part.add('Suppliers')
    fields(supplier, PartNumber='', Manufacturer='', Pattern='', Supplier='', SourceLocator='', Currency='')
    supplier.one('SourceLocator').annotations['asc_omit'] = 'not present in ASC'
    if not placed:
        fields(part, SubfolderIndex=-1)
        part.add('Verification', False, False, False, False, False, False, False)
        part.add('Groups')
        part.add('ModelNote', '')
        return part.bind_schema(CACHED_PART)
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
