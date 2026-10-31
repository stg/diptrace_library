"""Document-independent constructors for editable footprint content."""
from .model import Element
from .footprint_records import PAD, PATTERN, PATTERN_SHAPE, MODEL3D, VECTORS


def _fields(parent, **values):
    for name, value in values.items():
        parent.add(name, value)
    return parent


def new_pad(number='', name='', *, x=0, y=0, index=0):
    """Create pad data without document membership or format boundary slots."""
    pad = Element('Pad', index, number, name, x, y)
    for field in '''Number_New PadAngle PadWidth_New PadHeight_New PadHole PadHoleH
PadHoleType PadShape_New PadCorner PadShape_X PadShape_Y'''.split():
        pad.add(field, 0)
    _fields(pad, SurfacePad=False, Standard=False, Locked=False, Sided=False, Group=-1,
            DisableTopMask=0, DisableBottomMask=0, DisableTopPaste=0, DisableBottomPaste=0,
            CustomSwell_New=-1000, CustomShrink_New=-1000, PadMask_Percent=50,
            PadMask_EdgeGap=.9, PadMask_SegmentGap=.6, PadMask_SegmentSide=3)
    for collection in ('PadPoints_New', 'PadMask_TopSegments', 'PadMask_BotSegments'):
        pad.add(collection)
    return pad.bind_schema(PAD)


def new_pattern_drawing(index=0, *, kind=0):
    shape = Element('Shape', index)
    _fields(shape, Type=kind, Locked=False, Layer=0, FontName='', VectorFont=True,
            FontSize=6, FontScale=1, FontWidth=-1, TextShow=0, Width=.3,
            TextAngle=0, TextHorz=0, TextVert=0, TextAlign=0, LineSpacing=1.2,
            AllLayers=False, Group=-1, FontMono=False, PadId=-1)
    for collection in ('TextLine', 'Points_New'):
        shape.add(collection)
    return shape.bind_schema(PATTERN_SHAPE)


def new_model3d():
    """Create an empty physical-model attachment with shared library defaults."""
    model = Element('Model3D').bind_schema(MODEL3D)
    _fields(model, Model3DFile='', Model3DFile_Variable='', Mirror=False, NoSearch=False,
            Units=0, IPC_XOff=0, IPC_YOff=0, AutoHeight=0, AutoColor=0x4B4B4B,
            Type=0, KeepPins=False)
    for name, schema in VECTORS.items():
        value = 1 if name == 'Zoom' else 0
        _fields(model.add(name), X=value, Y=value, Z=value).bind_schema(schema)
    return model


def new_pattern(name=''):
    """Create an empty definition in its own local coordinate frame."""
    pattern = Element('Pattern', name)
    _fields(pattern, Type=0, VariableParameter1=False, VariableParameter2=False,
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
    for collection in ('InternalConnections', 'UserFields', 'PadPoints', 'Pattern_Groups',
                       'PadMask_TopSegments', 'PadMask_BotSegments', 'Dimensions', 'PossibleNames',
                       'Pattern_CategoryTypes', 'Pads', 'Shapes', 'Holes'):
        pattern.add(collection)
    pattern.append(new_model3d())
    return pattern.bind_schema(PATTERN)
