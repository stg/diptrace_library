"""Model-owned field vocabulary; adapters select their serialized order."""

PIN_FIELDS = '''Enabled Type Orientation Number NetNumber Length Name StringNumber
FConnect ShowName PinNumXShift PinNumYShift PinNameXShift PinNameYShift ElectricType
Hidden Locked ModelSig NoConnect NameFontSize NameFontWidth NameFontScale NetName
SignalDelay Group PinNameRotate PinNumRotate'''.split()

NET_FIELDS = '''Enabled UniteByName ConnectPinByName Locked ActiveLine ActivePoint
Number Width Clearance NetClass CustomColor WireColor Global Parts Lines'''.split()

LINE_FIELDS = '''Connect1 Connect2 ConnectL1 ConnectL2 ConnectB1 ConnectB2 Page
ConnectMode1 ConnectMode2 NetNumber Region Number Hidden Points Selected Group
CanUnhide Arrows'''.split()

PAD_FIELDS = '''Number Number_New Inverted Locked Sided DisableTopMask
DisableBottomMask DisableTopPaste DisableBottomPaste CustomSwell CustomShrink
CustomSwell_New CustomShrink_New PadWidth PadHeight PadHole PadHoleH PadHoleType
SurfacePad PadShape PadShape_New PadAngle PadShape_X PadShape_Y PadCorner
PadWidth_New PadHeight_New Group Standard Points PadPoints_New PadTerminalCount
PadTerminal PadMask_Percent PadMask_EdgeGap PadMask_SegmentGap PadMask_SegmentSide
PadMask_TopSegments PadMask_BotSegments'''.split()

PATTERN_FIELDS = '''Type VariableParameter1 VariableParameter2 VariableParameter3
VariableParameter4 VariableParameter5 InternalConnections Number1 Number2
Spacing1 Spacing2 Spacing3 LockProperties PatternOrientation Width Height
OriginCross OriginCircle OriginCommon OriginCourtyard Name_Description Name_Unique
RecoveryCode RecoveryCode_Generator RecoveryCode_Model Pattern_Manufacturer
PadCorner PadShape_X PadShape_Y PadWidth PadHeight PadShape SurfacePad PadHole
PadHoleH PadHoleType PadTerminalCount TopMask_State BotMask_State TopPaste_State
BotPaste_State CustomSwell_New CustomShrink_New PadMask_Percent PadMask_EdgeGap
PadMask_SegmentGap PadMask_SegmentSide PadMask_TopSegments PadMask_BotSegments
OriginX OriginY UserFields PadPoints Pattern_Groups Pads Shapes Holes Dimensions
Model3D Mounting Pattern_CategoryName Pattern_CategoryIndex Pattern_CategoryTypes
PossibleNames'''.split()

DIMENSION_FIELDS = '''Enabled Locked Type Connected1 Object1 SubObject1 Point1
Connected2 Object2 SubObject2 Point2 Layer X1 Y1 X2 Y2 XD YD ArrowSize Units
VectorFont FontName FontSize FontScale FontWidth ShowUnits Angle ExternalRadius
PointerMode PointerText Group'''.split()

SYMBOL_DRAWING_FIELDS = '''Enabled Orientation Type FontSize FontColor FontType
FontName Name PenWidth Points TextAngle TextHorz TextVert TextAlign LineSpacing
Group ShowPart MarkingGenerated TextLine Points_New Locked VectorFont FontWidth
FontScale'''.split()

COMPONENT_FIELDS = '''Enabled Selected Value BaseName BaseRefDes X Y Type Number1
Number2 Page Orientation Group Number Width Height ShowText TextAlign PartNumber
PartType PartName PartDescriptor AllowParts ShowText2 TextAlign2 ShowNumbers
TextPosX TextPosY TextPosX2 TextPosY2 PartString HiddenId UserFields FieldIndex1
FieldIndex2 Locked Angle LibPath LibPath_Variable ModelType ModelString
LockProperties Origin_X Origin_Y ModelBody Datasheet HorzFlip VertFlip ShowOrigin
PageHiddenId Manufacturer Component_CategoryName Component_CategoryIndex
Component_CategoryTypes CustomMarkingFont MarkingFontSize MarkingFontAll
ShowRefDes ShowName ShowValue ShowManufacturer ShowDatasheet Suppliers Pins Shapes
Pattern'''.split()

PAGE_FIELDS = '''Zones PageWidth PageHeight HorzZones VertZones ZoneStandard
ZoneFontName ZoneFontSize ZoneBorder HorzZoneBorder VertZoneBorder PageXPos
PageyPos PageScale PageType PageHiddenId FLeft FTop FRight FBottom'''.split()

SETTINGS_FIELDS = '''GridSize OriginEnabled clAxis BusConnectionFont PinNumberFont
PartFontSize PartFontColor UsePartFontColor GridEnabled GridSnap DisplayTitles
DisplaySheet BusConNetName BusConNetNumber ShowPinNumbers HidePinNumbers
BusConAbove BusConBelow BusLineWidth WireLineWidth TableLineWidth TitlesLineWidth
NodeSize UnitsMM UnitsMIL UnitsINCH ERC_PinType ERC_NotConnected ERC_SinglePin
ERC_Short ERC_VCCTemplate ERC_GNDTemplate ERC_PinSuperimpose'''.split()

SCHEMATIC_DRAWING_FIELDS = '''Enabled Selected Orientation Type FontSize FontColor
Color BrushColor FontType Page Group PenWidth FontName Name BitmapIndex Points
RelatedNet RelatedBus Locked VectorFont FontWidth FontScale Picture_Width
Picture_Height Picture_Transparent Picture_File Picture_File_Variable
Picture_Proportions TextHorz TextVert TextAlign TextAngle LineSpacing TextLine
Points_New'''.split()

PAGE_CONNECTOR_FIELDS = '''Enabled Selected Connected Page BusNumber Number Region
Group Locked'''.split()

BUS_FIELDS = '''Enabled Locked Numbers ActiveLine ActivePoint Number Region Nets Lines'''.split()

BUS_LINE_FIELDS = '''Connect1 Connect2 ConnectL1 ConnectL2 ConnectB1 ConnectB2 Page
ConnectMode1 ConnectMode2 BusNumber Region Number Points Selected Group'''.split()

TABLE_FIELDS = '''Enabled Selected Locked DefVectorFont DefFontWidth DefFontScale
HideBorder Layer DefAlign DefFontSize Orientation Group DefFontColor DefCellWidth
DefCellHeight X1 Y1 X2 Y2 DefFontName Name Page DefLineSpacing ColWidths RowHeights
Cells'''.split()

CELL_FIELDS = '''FOrientation FontSize FontType Align FontColor Text TextLine
FontName VectorFont FontWidth FontScale LineSpacing'''.split()

CACHED_PIN_FIELDS = '''Enabled Locked ModelSig Type Orientation Number Length Name
StringNumber ShowName PinNumXShift PinNumYShift PinNameXShift PinNameYShift
ElectricType NameFontSize NameFontWidth NameFontScale Group PinNameRotate
PinNumRotate'''.split()

CACHED_DRAWING_FIELDS = '''Enabled Locked VectorFont FontWidth FontScale
Orientation Type FontSize FontColor FontType FontName Name PenWidth Points
TextAngle TextHorz TextVert TextAlign LineSpacing Group TextLine Points_New
ShowPart MarkingGenerated'''.split()

CACHED_SYMBOL_FIELDS = '''Enabled PartType PartName ShowNumbers Type Number1
Number2 Width Height Value LockProperties Origin_X Origin_Y Pins Shapes UserFields
ModelType ModelString ModelBody SubfolderIndex Verification Manufacturer
Component_CategoryName Component_CategoryIndex Component_CategoryTypes Groups
Suppliers'''.split()

CACHED_PATTERN_FIELDS = '''Type Datasheet VariableParameter1 VariableParameter2
VariableParameter3 VariableParameter4 Number1 Number2 Spacing1 Spacing2
VariableParameter5 Spacing3 LockProperties PatternOrientation Width Height
OriginCross OriginCircle OriginCommon OriginCourtyard Name_Description Name_Unique
RecoveryCode RecoveryCode_Generator RecoveryCode_Model Pattern_Manufacturer
PadCorner PadShape_X PadShape_Y PadWidth PadHeight PadShape PadHole PadHoleH
PadHoleType PadTerminalCount PadMask_Percent PadMask_EdgeGap PadMask_SegmentGap
PadMask_SegmentSide PadMask_TopSegments PadMask_BotSegments SurfacePad OriginX
OriginY PadPoints InternalConnections Pattern_Groups Pads Shapes Holes Dimensions
UserFields Model3D Mounting Pattern_CategoryName Pattern_CategoryIndex
Pattern_CategoryTypes PossibleNames'''.split()

SCHEMATIC_FIELDS = '''Pages PictureCount ShowText TextAlign ShowText2 TextAlign2
HidePower OriginX OriginY FieldName1 FieldName2 PartFontVector ProjectDir
PartFontWidth PartFontScale NetClasses DifferentialPairs ShowRefDes_Global
ShowName_Global ShowValue_Global ShowManufacturer_Global ShowDatasheet_Global
ShowUserfield_Global Components PageConnectors Shapes Nets Buses Groups Tables
Settings ssimulator ProjectLibs_Name ProjectLibs_Type ProjectLibs_Content
ProjectLibs_Folders ProjectLibs_Libs ProjectLibs_Sorted DesignCache_Count
DesignCache_Links CacheLib'''.split()


PAD_STYLE_FIELDS = '''SurfacePad Sided PadHoleType PadHole PadHoleH PadShape
PadWidth PadHeight PadCorner PadShape_X PadShape_Y PadPoints PadTerminalCount
PadTerminal TopMask_State BotMask_State TopPaste_State BotPaste_State
CustomSwell_New CustomShrink_New PadMask_Percent PadMask_EdgeGap
PadMask_SegmentGap PadMask_SegmentSide PadMask_TopSegments PadMask_BotSegments'''.split()


# Compatibility occurrences belong to import modernization and destination
# projection. They are not independent editable properties of the current model.
GLOBAL_COMPATIBILITY_FIELDS = ('ShowText', 'ShowText2', 'TextAlign', 'TextAlign2',
                               'FieldName1', 'FieldName2')
COMPONENT_COMPATIBILITY_FIELDS = ('ShowText', 'TextAlign', 'ShowText2', 'TextAlign2',
                                  'TextPosX', 'TextPosY', 'TextPosX2', 'TextPosY2',
                                  'FieldIndex1', 'FieldIndex2', 'Orientation')
PAD_COMPATIBILITY_FIELDS = ('Number', 'Inverted', 'PadWidth', 'PadHeight', 'PadShape',
                            'Points', 'CustomSwell', 'CustomShrink')
DRAWING_COMPATIBILITY_FIELDS = ('Name', 'Orientation', 'Points')

COMPONENT_MODEL_FIELDS = tuple(name for name in COMPONENT_FIELDS if name not in COMPONENT_COMPATIBILITY_FIELDS)
SCHEMATIC_MODEL_FIELDS = tuple(name for name in SCHEMATIC_FIELDS if name not in GLOBAL_COMPATIBILITY_FIELDS)
PAD_MODEL_FIELDS = tuple(name for name in PAD_FIELDS if name not in PAD_COMPATIBILITY_FIELDS)
SYMBOL_DRAWING_MODEL_FIELDS = tuple(name for name in SYMBOL_DRAWING_FIELDS if name not in DRAWING_COMPATIBILITY_FIELDS)
SHEET_DRAWING_MODEL_FIELDS = tuple(name for name in SCHEMATIC_DRAWING_FIELDS if name not in DRAWING_COMPATIBILITY_FIELDS)
PATTERN_DRAWING_FIELDS = '''Type Locked Layer TextLine FontName VectorFont FontSize
FontScale FontWidth FontMono TextShow Width Points_New TextAngle TextHorz TextVert
TextAlign LineSpacing AllLayers Group PadId'''.split()
