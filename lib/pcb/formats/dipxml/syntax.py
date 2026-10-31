"""PCB XML syntax over the common XML codec, before model normalization."""
from pathlib import Path

from ....common import xml
from ...model.document import Document


_NUMBERS = frozenset('''
Id UpdateId Index Count X Y Z X1 Y1 X2 Y2 XD YD Width Height Angle Orientation
Float1 Float2 Float3 Int1 Int2 Hole HoleH Corner XOff YOff Segment_Percent
Segment_EdgeGap Segment_Gap Segment_Side CustomSwell CustomShrink Diam HoleDiam
IPC_XOff IPC_YOff AutoHeight AutoColor FontSize FontSizeFloat FontWidth FontScale
FontColor TextWidth TextHeight LineWidth LineSpacing Object1 Object2 SubObject1
SubObject2 Point1 Point2 ArrowSize ExternalRadius NetId
InternalConnection NetClass MarkingFontSize MarkingFontSizeFloat
SignalDelay
PlacementClearance Group ShieldGroup TraceShieldGroup ViaStyle SubFolderIndex Number
PadVia Smd Trace TJunc PadViaWidth PadViaLength SmdWidth SmdLength TraceLength TJuncLength
Comp Pad Lay PairPoint PairSubPoint PairSeparateTrace Jumper Meander PhaseFwd PhaseBack
MeanderAngle DrawX DrawY Width Clearance MeanderGap HiddenId TraceColor
ActiveLine ActivePoint
Size HoleSize Lay1 Lay2
PlaneRing Color Thickness Constant TraceWidth
Phase Phase_ErrorLength LengthDelta FixedLength MaxUncoupledLength Tolerance
MinWidth MaxWidth DifClearance Neck_Width Neck_DifClearance Neck_MaxLength
PriorityValue MaxViasValue MaxIncorrectWayValue
TraceToTrace TraceToVia TraceToPad TraceToSmd TraceToCopper
ViaToVia ViaToPad ViaToSmd ViaToCopper PadToPad PadToSmd PadToCopper SmdToSmd SmdToCopper
Columns Rows ColumnSpacing RowSpacing RailLeft RailRight RailTop RailBottom
TabWidth TabRadius TabStep HoleDiam HoleStep HoleInset HoleKeepout CombinedRadius BorderTabs
LeftGap RightGap TopGap BottomGap
FieldId
PosNet NegNet PosTrace NegTrace PosComp PosPad NegComp NegPad TraceId
StartPoint EndPoint StartSegment EndSegment PosTrace_StartPoint PosTrace_EndPoint
NegTrace_StartPoint NegTrace_EndPoint PosTraceSide PosShieldGroup NegShieldGroup
NetClass1 NetClass2 SilkClearance SameTraceToTrace SameSmdToVia SameSmdToPad SameSmdToSmd
MinTrace MinDrill MinRing MaxRing MaxPlatedHole MaxNonPlatedHole
TraceToDrill TraceToBoard ViaToDrill ViaToBoard PadToDrill PadToBoard
SmdToDrill SmdToBoard CopperToCopper CopperToDrill CopperToBoard DrillToDrill DrillToBoard
Comp1 Comp2 Pad1 Pad2 Delta Length
MinimumArea Priority BoardClearance SpokeWidth SMD_SpokeWidth PictureWidth PictureHeight PictureTransparent
NonSignal CellWidth CellHeight AssemblyVariant PickOffX PickOffY
NumXShift NumYShift NameXShift NameYShift NumOrientation NameOrientation
PadId Scale
'''.split()) | frozenset({('UId', 'Name'), ('Column', 'Type')}) | frozenset(('DesignError', name) for name in
    ('Value', 'Rule', 'RuleLay', 'ExtObject1', 'ExtObject2', 'ObjectNetClass1', 'ObjectNetClass2'))
_FLAGS = frozenset('''
Enabled Selected Hidden Locked AllLayers FontVector FontMono DefStyle LockTypeChange
Cross Circle Mirror NoSearch KeepPins Generator Model Flip HorzFlip
PanelExclude CustomMarkingFont MarkingFontAll ShowUnits
Arc PairNecked HideRatlines ShowLength CustomColor AllowLoops Highlighted
Through
VariableThickness
CheckLength AllVias PerformDRC RoutePriority RouteMaxVias RouteMaxIncorrectWay RouteAllLayers
PanelizeSingle RailShow TabsDone KeepMaterial
TopLine BottomLine LeftLine RightLine
ConnectAll
AutoPadPoints Necked PhaseError
CheckClearance CheckSize CheckJumpers CheckCopperPours CheckCoperPours CheckClassToClass CheckSilk
CheckKeepouts CheckSameNet CheckSameComponentPads CheckCourtyard
AnyError Error HideBorder Header BomRowNumber BomTotal PickMirror PickOrigin
ShowName
Poured UseNetClearance SnapToBoard IslandRegion IslandInternal IslandConnection ViaDirect SMD_Separate RegionsDone
Inverted PictureRaster PictureProportions PictureFlipped
'''.split())
_FLAGS |= frozenset(('LayerPanel', name) for name in '''TopAssy TopMask TopPaste BotAssy BotMask BotPaste Board
    TopTerminals BotTerminals TopCourtyard BotCourtyard TopOutline BotOutline TopDimensions BotDimensions'''.split())
_FLAGS |= frozenset(('ConnectivityCheck', name) for name in ('Traces', 'Shapes', 'CopperPours'))
_FLAGS |= frozenset({('ProjectLibs', 'Sorted')})
DIALECT = xml.XmlDialect(format='dipxml', source_type='DipTrace-PCB', representation='dipxml',
    number_attributes=_NUMBERS, boolean_attributes=_FLAGS,
    boolean_text=frozenset('''DisplayTitles DisplaySheet Visible Border Snap YIdentical CompRotate FontVector FontMono
        StackLength SignalDelayLength ShowCompFiducials EditInactiveLayer TopComponentLock
        BottomComponentLock LockNetStructure FlipTextAuto SchemNetClasses ShowList DRCDone'''.split())
        | frozenset(('Assembly', name) for name in ('Pads', 'Silk', 'CompBorders', 'BoardOutline'))
        | frozenset({('Lays', 'Item')}),
    number_text=frozenset({(parent, 'Item') for parent in
                         ('ColWidths', 'ColumnWidths', 'RowHeights', 'ConnectedTeardrops', 'HorzTabsX', 'VertTabsY',
                          'HideRingLay', 'BlindLay')}
                         | {('AllowedVias', 'ViaStyle'), ('HierarchyPath', 'Item'), ('PadId', 'Item'),
                            ('RowCom', 'Item'), ('AssemblyExclude', 'Item')}
                         | {(parent, name) for parent, names in (
                             ('SheetSettings', 'Xpos Ypos Scale SheetWidth SheetHeight LeftMargin TopMargin RightMargin BottomMargin'),
                             ('BorderZones', 'HorzZones VertZones Standard FontSize FontSizeFloat FontLineWidth HorzBorderSize VertBorderSize'),
                             ('Markings', 'FontSize FontSizeFloat FontWidth FontScale'),
                             ('Grid', 'Size YSize'), ('Origin', 'X Y AxisColor'),
                             ('LineWidth', 'Silk Table Titles BoardOutline Assembly CompOutline Courtyard'),
                             ('Routing', 'TraceWidth TraceClearance BoardClearance ViaSize ViaHole FanoutLength'),
                             ('DRC', 'RealTimeMode'), ('LastDRC', 'RealTimeMode'),
                             ('Settings', 'SolderMaskSwell PasteMaskShrink')) for name in names.split()}))


def loads(data, *, source=None):
    return xml.loads(data, source=source, dialect=DIALECT, document_factory=Document)


def read(path):
    path = Path(path)
    return loads(path.read_bytes(), source=str(path))


def dumps(document, *, newline='\n'):
    return xml.dumps(document, newline=newline, dialect=DIALECT)
