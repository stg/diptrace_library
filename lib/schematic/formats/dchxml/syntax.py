"""Schematic XML vocabulary over the shared XML syntax codec."""
from pathlib import Path

from ....common import xml
from ....common.xml import set_attribute
from ...model.document import Document


_NUMBER_ATTRIBUTES = set("""
Angle ArrowSize AutoColor AutoHeight BlockId Bus1 Bus2 BusId Clearance Color ComponentPart Group HiddenId
Corner Count CustomShrink CustomSwell Diam DifClearance Dir ExternalRadius
Float1 Float2 Float3 Font FontColor FontScale FontSize FontWidth Height Hole
FontSizeFloat MarkingFontSizeFloat TextWidth TextHeight ConductanceSteps Iteration TransferCurveIteration
LowIteration PointIteration TotalIteration SourceStepping MethodMaxOrder Method
HoleDiam HoleH IPC_XOff IPC_YOff Id Index Int1 Int2 Length LineSpacing LineWidth
MarkingFontSize MaxUncoupledLength NameOrientation NameXShift NameYShift NegNet
NetClass NetId NumOrientation NumXShift NumYShift Number Object1 Object2
Orientation PadId Part PartNumber Phase Phase_ErrorLength PictureHeight
PictureTransparent PictureWidth Pin Point1 Point2 PointerMode PosNet Scale
Segment_EdgeGap Segment_Gap Segment_Percent Segment_Side Sheet SignalDelay Size
SubObject1 SubObject2 Tolerance UpdateId Width X X1 X2 XD XOff Y Y1 Y2 YD YOff Z
WireColor ConnectionNumber CellWidth CellHeight FieldId GndNetId
""".split())
_BOOLEAN_ATTRIBUTES = set("""
AllLayers AllowParts CanUnhide CheckNotConnected CheckPinSuperimpose CheckPinType
CheckShort CheckSinglePin Circle Cross FontVector Generator HiddenPower HorzFlip
KeepPins LockTypeChange Locked Mirror Model NoSearch PictureProportions ShowName
Selected Enabled UniteByName ConnectPinByName Global CustomColor
ShowOrigin CustomMarkingFont MarkingFontAll NotConnected
FontMono PictureFlipped NoPrintStat NoPrintModelParams SkipConductanceStepping StartFromConductanceStepping NoOPAnalysis
DefStyle
ShowUnits Sorted VertFlip Visible Connected HideBorder TopLine BottomLine LeftLine RightLine Plotted
""".split())
_BOOLEAN_TEXT = set("""
Border DisplaySheet DisplayTitles FontVector HidePower Snap UsePartFontColor Visible
FontMono
""".split())
_NUMBER_TEXT = {
    **{('Sheet', name): True for name in """
        Id XPos YPos Scale SheetWidth SheetHeight LeftMargin TopMargin RightMargin
        BottomMargin BlockId""".split()},
    **{('BorderZones', name): True for name in """
        HorzZones VertZones Standard FontSize FontLineWidth HorzBorderSize
        VertBorderSize""".split()},
    **{('Markings', name): True for name in 'FontSize FontWidth FontScale FontColor'.split()},
    **{('Origin', name): True for name in 'AxisColor X Y'.split()},
    **{('LineWidth', name): True for name in 'Wire NodeSize Bus Table Titles'.split()},
    ('Grid', 'Size'): True,
    ('BusConnections', 'FontSize'): True,
    ('SheetSettings', 'ActiveSheet'): True,
    **{(parent, 'FontSizeFloat'): True for parent in ('BorderZones', 'Markings', 'BusConnections')},
    **{(parent, 'Item'): True for parent in ('ColWidths', 'ColumnWidths', 'RowHeights')},
}


DIALECT = xml.XmlDialect(format='dchxml', source_type='DipTrace-Schematic',
    representation='dchxml', number_attributes=frozenset(_NUMBER_ATTRIBUTES),
    boolean_attributes=frozenset(_BOOLEAN_ATTRIBUTES), boolean_text=frozenset(_BOOLEAN_TEXT),
    number_text=frozenset(_NUMBER_TEXT))


def loads(data, *, source=None):
    document = xml.loads(data, source=source, dialect=DIALECT, document_factory=Document)
    from .refs import bind_references
    bind_references(document)
    return document


def read(path):
    path = Path(path)
    return loads(path.read_bytes(), source=str(path))


def dumps(document, *, newline='\n'):
    return xml.dumps(document, newline=newline, dialect=DIALECT)
