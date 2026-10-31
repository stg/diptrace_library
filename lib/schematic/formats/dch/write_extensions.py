"""Named schema-46 extension records, shared by placed and cached content."""
from ...model.traversal import (placed_components, cached_definitions, footprints, symbols)
from ...model.simulation import argument_values
from ....common.footprint_codec import write_pattern_extensions
from ....common.drawing_codec import write_text_properties
from ....common.symbol_codec import write_symbol_extensions
from ....common.supplier_codec import write_supplier
from ....common.binary_records import write_grid_step


def simulation_arguments(writer, group):
    values = argument_values(group)
    writer.integer(len(values))
    for value in values:
        writer.text(value.value)


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
    write_grid_step(writer,settings.scalar('GridSize'))


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
        write_pattern_extensions(writer,part.one('Pattern'))
        write_symbol_extensions(writer,part,placed=True)
    for shape in schematic.select('Shapes/Shape'):
        write_text_properties(writer,shape)
    for table in schematic.select('Tables/Table'):
        writer.field(table,'DefLineSpacing','number')
        for cell in table.select('Cells/Cell'):
            writer.field(cell,'LineSpacing','number')
    for page in schematic.select('Pages/Page'):
        for content in page.select('TitleBlocks/TitleBlock/Contents/Content'):
            writer.field(content,'LineSpacing','number')
    for definition in cached_definitions(schematic):
        write_pattern_extensions(writer,definition.one('Pattern'))
        write_symbol_extensions(writer,definition.one('Part'))


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
        write_supplier(writer, part, prices=part.parent.kind=='Components')
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
