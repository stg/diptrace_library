"""Named schema-46 extension records, shared by placed and cached content."""
from ...model.traversal import (placed_components, cached_definitions, footprints, symbols)
from ...model.simulation import argument_values


def simulation_arguments(writer, group):
    values = argument_values(group)
    writer.integer(len(values))
    for value in values:
        writer.text(value.value)


def _angle(writer,parent,name):
    writer.field(parent,name,'number')


def _terminals(writer,parent):
    records=parent.children('PadTerminal')
    writer.integer(len(records))
    for terminal in records:
        writer.field(terminal,'Type','integer')
        writer.fields(terminal,'number','X Y')
        _angle(writer,terminal,'Angle')
        writer.fields(terminal,'number','ShapeWidth ShapeHeight ShapeCorner')
        writer.rows(terminal.one('ShapePoints'),'pt','number number')


def _mask_segments(writer,parent):
    for name in ('PadMask_TopSegments','PadMask_BotSegments'):
        writer.rows(parent.one(name),'pt','number '*4)


def _drawing_text(writer,shape):
    _angle(writer,shape,'TextAngle')
    writer.fields(shape,'integer','TextHorz TextVert TextAlign')
    writer.field(shape,'LineSpacing','number')
    writer.rows(shape.one('TextLine'),'pt','text')


def _pattern(writer,pattern):
    writer.fields(pattern,'boolean','OriginCross OriginCircle')
    writer.field(pattern,'OriginCommon','integer')
    writer.field(pattern,'OriginCourtyard','integer')
    writer.fields(pattern,'text','Name_Description Name_Unique RecoveryCode')
    writer.fields(pattern,'boolean','RecoveryCode_Generator RecoveryCode_Model')
    writer.field(pattern,'Pattern_Manufacturer','text')
    writer.fields(pattern,'number','PadCorner PadShape_X PadShape_Y')
    _terminals(writer,pattern)
    writer.fields(pattern,'integer','TopMask_State BotMask_State TopPaste_State BotPaste_State')
    writer.fields(pattern,'number','CustomSwell_New CustomShrink_New PadMask_Percent PadMask_EdgeGap PadMask_SegmentGap PadMask_SegmentSide')
    _mask_segments(writer,pattern)
    for pad in pattern.select('Pads/Pad'):
        writer.field(pad,'Group','integer')
        writer.field(pad,'PadCorner','number')
        _angle(writer,pad,'PadAngle')
        writer.fields(pad,'number','PadShape_X PadShape_Y')
        _terminals(writer,pad)
        writer.fields(pad,'number','PadMask_Percent PadMask_EdgeGap PadMask_SegmentGap PadMask_SegmentSide')
        _mask_segments(writer,pad)
    for shape in pattern.select('Shapes/Shape'):
        for point in shape.select('Points_New/pt'):
            writer.values(point,'number number')
        _drawing_text(writer,shape)
        writer.field(shape,'AllLayers','boolean')
        writer.field(shape,'Group','integer')
    for hole in pattern.select('Holes/Hole'):
        writer.integer(hole.values[6])
    for dimension in pattern.select('Dimensions/Dimension'):
        writer.field(dimension,'Group','integer')
    writer.rows(pattern.one('Pattern_Groups'),'pt','boolean integer number number')
    model=pattern.one('Model3D')
    writer.fields(model,'number','IPC_XOff IPC_YOff AutoHeight')
    writer.field(model,'AutoColor','color')
    writer.field(model,'Type','integer')


def _symbol(writer,part,*,placed):
    for pin in part.select('Pins/Pin'):
        writer.field(pin,'Group','integer')
    for shape in part.select('Shapes/Shape'):
        _drawing_text(writer,shape)
        writer.field(shape,'Group','integer')
        if placed:
            writer.fields(shape,'boolean','ShowPart MarkingGenerated')
    if not placed:
        writer.rows(part.one('Groups'),'pt','boolean integer number number')


def common(writer,document):
    schematic=document.one('/Schematic')
    for row in schematic.select('NetClasses/NetClass'):
        writer.values(row,'number '*5,start=5)
    pairs=schematic.select('DifferentialPairs/DifferentialPair')
    writer.integer(len(pairs))
    for pair in pairs:
        writer.boolean(pair.values[1])
        writer.text(pair.values[0])
        writer.values(pair,'integer integer integer boolean color',start=2)
    writer.fields(document.root,'number','Xpos Ypos')
    for page in schematic.select('Pages/Page'):
        writer.fields(page,'number','PageXPos PageyPos')
    for part in placed_components(schematic):
        for pin in part.select('Pins/Pin'):
            writer.field(pin,'SignalDelay','number')
    for pattern in footprints(schematic):
        for pad in pattern.select('Pads/Pad'):
            for name in ('DisableTopMask','DisableBottomMask','DisableTopPaste','DisableBottomPaste'):
                writer.field(pad,name,'integer')
    settings=schematic.one('Settings')
    grid=float(settings.scalar('GridSize'))
    # Scale small spacings before the fixed-point codec quantizes them. The
    # denominator is destination bookkeeping, not another editable grid value.
    divisor=max(1,min(100000,round(1000/grid))) if grid>=.000001 else 100000
    writer.number(grid*divisor)
    writer.integer(divisor)


def drawings(writer,schematic):
    for name,size in [('ShowRefDes_Global',3),('ShowName_Global',3),('ShowValue_Global',2),
                      ('ShowManufacturer_Global',2),('ShowDatasheet_Global',2)]:
        writer.values(schematic.one(name),'integer '*size)
    writer.rows(schematic.one('ShowUserfield_Global'),'pt','text text integer integer')
    for part in placed_components(schematic):
        writer.field(part,'CustomMarkingFont','boolean')
        writer.field(part,'MarkingFontSize','integer')
        writer.field(part,'MarkingFontAll','boolean')
        for name,size in [('ShowRefDes',5),('ShowName',5),('ShowValue',4),('ShowManufacturer',4),('ShowDatasheet',4)]:
            writer.values(part.one(name),'integer '*size+'number '*3)
        for user in part.select('UserFields/UserField'):
            writer.values(user,'integer '*4+'number '*3,start=3)
        _pattern(writer,part.one('Pattern'))
        _symbol(writer,part,placed=True)
    for shape in schematic.select('Shapes/Shape'):
        _drawing_text(writer,shape)
    for table in schematic.select('Tables/Table'):
        writer.field(table,'DefLineSpacing','number')
        for cell in table.select('Cells/Cell'):
            writer.field(cell,'LineSpacing','number')
    for page in schematic.select('Pages/Page'):
        for content in page.select('TitleBlocks/TitleBlock/Contents/Content'):
            writer.field(content,'LineSpacing','number')
    for definition in cached_definitions(schematic):
        _pattern(writer,definition.one('Pattern'))
        _symbol(writer,definition.one('Part'),placed=False)


def project(writer,schematic):
    writer.field(schematic.one('Settings'),'PartFontSize','integer')
    writer.field(schematic.one('Settings'),'PartFontColor','color')
    writer.field(schematic.one('Settings'),'UsePartFontColor','boolean')
    for part in symbols(schematic):
        for pin in part.select('Pins/Pin'):
            writer.fields(pin,'integer','PinNameRotate PinNumRotate')
    for shape in schematic.select('Shapes/Shape'):
        writer.fields(shape,'number','Picture_Width Picture_Height Picture_Transparent')
        writer.field(shape,'Picture_File','text')
        writer.field(shape,'Picture_Proportions','boolean')
    for pattern in footprints(schematic):
        writer.field(pattern.one('Model3D'),'KeepPins','boolean')
    for part in symbols(schematic):
        supplier=part.one('Suppliers')
        writer.fields(supplier,'text','PartNumber Manufacturer Pattern Supplier SourceLocator Currency')
        if part.parent.kind=='Components':
            writer.rows(supplier.one('Prices'),'Quote','integer number')
    for part in placed_components(schematic):
        writer.field(part.one('Suppliers'),'MainSupplier','boolean')
    for part in placed_components(schematic):
        writer.field(part,'LibPath_Variable','text')
        writer.field(part.one('Pattern/Model3D'),'Model3DFile_Variable','text')
    for shape in schematic.select('Shapes/Shape'):
        writer.field(shape,'Picture_File_Variable','text')
    for name,kind in [('ProjectLibs_Folders','Folder'),('ProjectLibs_Libs','Lib')]:
        for path in schematic.select(name+'/'+kind):
            writer.field(path,'VariablePath','text')
    for slot in schematic.select('CacheLib/Slots/Slot'):
        writer.field(slot,'VariablePath','text')
        definitions=slot.children('Definition')
        model=definitions[0].one('Pattern/Model3D') if definitions else slot
        writer.field(model,'Model3DFile_Variable','text')
    writer.field(schematic,'ProjectDir','text')
    simulation=schematic.one('ssimulator')
    writer.field(simulation,'tp','integer')
    signals=simulation.select('signals/signal')
    writer.integer(len(signals))
    for signal in signals:
        writer.fields(signal,'integer','signal_tp signal_num')
        writer.field(signal,'signal_display_name','text')
        writer.fields(signal,'boolean','signal_plotted signal_visible')
        writer.field(signal,'signal_color','color')
    for name in ('sim_ac','sim_dc','sim_tran','sim_noise'):
        simulation_arguments(writer, simulation.one(name))
    writer.field(simulation,'gndnum','integer')
    writer.field(simulation,'gndname','text')
