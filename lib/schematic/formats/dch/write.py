"""Binary output through schema 52 by named traversal, without source replay."""
from ....common.binary import NUMBER_LIMIT
from ....common.binary_records import RecordWriter
from ....common.footprint_codec import (write_parameters, write_pad_geometry,
                                        write_holes, write_model)
from ....common.dimension_codec import write_dimension_properties
from ....common.title_block_codec import write_title_block, write_text_content
from ....common.catalog_codec import write_category_types
from ....common.library_codec import LibraryCodecs, write_definition, write_library_cache
from ....common.symbol_codec import write_symbol_drawings
from .records import (COMPONENT_PLACEMENT, PIN_FONT)
from ..capabilities import DCH
from ....common.conversion import (export_diagnostics)
from ....common.pad_masks import MASK_FIELDS, mask_state
from decimal import Decimal
import math


def legacy_pad_orientation(angle):
    """The binary compatibility flag describes positive upright quarter turns."""
    angle=float(angle)
    return abs(angle-math.pi/2)<.001 or abs(angle-3*math.pi/2)<.001


class Writer(RecordWriter):
    format_name = 'DCH'

    def __init__(self,version=DCH.default_write_version,*,compatibility_changes=None):
        super().__init__()
        self.version=version
        self.compatibility_changes = compatibility_changes if compatibility_changes is not None else []

    def compatibility_values(self,node,values=None,*,width=2):
        """Project redundant drawing coordinates within the DCH writer range."""
        values = node.values if values is None else tuple(values)
        if len(values) != width:
            raise ValueError(f'{node.path}: expected {width} binary tuple values, found {len(values)}')
        for value in values:
            if not isinstance(value, bool) and isinstance(value, (int, float, Decimal)):
                number = float(value)
                if math.isfinite(number) and not -NUMBER_LIMIT <= number <= NUMBER_LIMIT:
                    value = min(NUMBER_LIMIT, max(-NUMBER_LIMIT, number))
                    self.compatibility_changes.append(node)
            self.number(value)

    def field_value(self,parent,name,codec,value):
        if codec == 'integer' and name in ('FontSize', 'NameFontSize', 'MarkingFontSize',
                'DefFontSize', 'PartFontSize', 'PinNumberFont', 'BusConnectionFont', 'ZoneFontSize'):
            from ....common.font_codec import compatibility_size
            return compatibility_size(value)
        return super().field_value(parent, name, codec, value)

    def first_text_line(self,shape):
        lines=shape.one('TextLine').children('pt')
        self.text(lines[0].values[0] if lines else '')

    def pattern_parameters(self,pattern):
        write_parameters(self,pattern)

    def pads(self,pattern):
        pads=pattern.one('Pads').children('Pad')
        self.integer(len(pads))
        for pad in pads:
            self.boolean(legacy_pad_orientation(pad.scalar('PadAngle')))
            self.field(pad,'Number_New','integer')
            self.number(pad.values[3])
            self.number(pad.values[4])
            self.text(pad.values[1])
            self.text(pad.values[2])
            write_pad_geometry(self,pad)
            self.fields(pad,'boolean','Locked Sided')
            for name in MASK_FIELDS:
                self.boolean(mask_state(pad,name)==2)
            self.fields(pad,'number','CustomSwell_New CustomShrink_New')

    def pattern_graphics(self,pattern):
        shapes=pattern.one('Shapes').children('Shape')
        self.integer(len(shapes))
        for shape in shapes:
            self.field(shape,'Type','integer')
            geometry = shape.one('Points_New')
            width,height=(float(pattern.scalar(name)) for name in ('Width','Height'))
            normalized=[]
            for point in geometry.children():
                if point.kind != 'pt' or len(point.arguments) != 2:
                    raise ValueError(f'{point.path}: expected pt binary row with two coordinates')
                if any(value.kind != 'number' or value.unit for value in point.arguments):
                    raise TypeError(f'{point.path}: drawing coordinates require unqualified numbers')
                if not width or not height:
                    raise ValueError(f'{pattern.path}: compatibility points require nonzero dimensions')
                normalized.append((float(point.values[0])/width,float(point.values[1])/height))
            # The earlier view has two vertices for simple drawings and a third
            # for an arc. Modern polylines use their complete point array below.
            corners=[0.]*6
            kind=shape.scalar('Type')
            if 0<kind<8:
                for index,point in enumerate(normalized[:3 if kind==6 else 2]):
                    corners[index*2:index*2+2]=point
            self.compatibility_values(shape,corners,width=6)
            self.field(shape,'Locked','boolean')
            self.field(shape,'Layer','integer')
            self.first_text_line(shape)
            self.field(shape,'FontName','text')
            self.field(shape,'VectorFont','boolean')
            self.field(shape,'FontSize','integer')
            self.fields(shape,'number','FontScale FontWidth')
            self.integer(round(float(shape.scalar('TextAngle'))/(math.pi/2)))
            self.field(shape,'TextShow','integer')
            self.field(shape,'Width','number')
            self.integer(len(normalized))
            for point,values in zip(geometry.children(),normalized):
                self.compatibility_values(point,values)
        write_holes(self,pattern.one('Holes').children('Hole'))
        dimensions=pattern.one('Dimensions').children('Dimension')
        self.integer(len(dimensions))
        for dimension in dimensions:
            self.fields(dimension,'boolean','Enabled Locked')
            write_dimension_properties(self,dimension)

    def model3d(self,pattern):
        write_model(self,pattern)

    def symbol_shapes(self, part):
        from ...model.angles import quarter_turns
        write_symbol_drawings(self, part,
            orientation=lambda angle: quarter_turns(angle, full_turn=math.tau),
            placed=part.parent.kind == 'Components')

    def placed_pins(self,part):
        pins=part.one('Pins').children('Pin')
        self.integer(len(pins))
        for pin in pins:
            self.field(pin,'Enabled','boolean')
            self.fields(pin,'integer','Type Orientation Number NetNumber')
            self.values(pin,'number number',start=1)
            self.field(pin,'Length','number')
            self.fields(pin,'text','Name StringNumber')
            self.fields(pin,'boolean','FConnect ShowName')
            self.fields(pin,'number','PinNumXShift PinNumYShift PinNameXShift PinNameYShift')
            self.field(pin,'ElectricType','integer')
            self.fields(pin,'boolean','Hidden Locked')
            self.field(pin,'ModelSig','text')
            self.field(pin,'NoConnect','boolean')
            for name,codec in PIN_FONT:
                self.field(pin,name,codec)

    def component(self,part):
        for name,codec in COMPONENT_PLACEMENT:
            if name == 'Orientation':
                from ..asc.policy import (component_orientation)
                self.integer(component_orientation(part))
            else:
                self.field(part,name,codec)
        self.values(part,'text text')
        self.fields(part,'text','Value BaseRefDes BaseName')
        self.integer(0)
        self.integer(0)
        self.field(part,'LockProperties','boolean')
        self.fields(part,'integer','PartNumber PartType')
        self.fields(part,'text','PartName PartDescriptor')
        self.field(part,'AllowParts','boolean')
        self.integer(0)
        self.integer(0)
        self.field(part,'ShowNumbers','integer')
        for _ in range(4):
            self.number(0)
        self.field(part,'PartString','text')
        self.field(part,'HiddenId','integer')
        self.rows(part.one('UserFields'),'UserField','text text integer',trailing=7)
        self.integer(-1)
        self.integer(-1)
        self.field(part,'Locked','boolean')
        self.number(math.radians(float(part.scalar('Angle'))))
        self.field(part,'LibPath','text')
        self.field(part,'ModelType','integer')
        self.rows(part.one('ModelBody'),'Line','text')
        self.fields(part,'text','ModelString Datasheet')
        self.fields(part,'boolean','HorzFlip VertFlip')
        self.placed_pins(part)
        self.symbol_shapes(part)
        pattern=part.one('Pattern')
        self.rows(pattern.one('InternalConnections'),'IntCon','integer integer')
        self.pattern_parameters(pattern)
        self.fields(part,'number','Origin_X Origin_Y')
        self.field(part,'ShowOrigin','boolean')
        self.rows(pattern.one('UserFields'),'UserField','text text integer')
        self.rows(pattern.one('PadPoints'),'pt','number number')
        self.pads(pattern)
        self.pattern_graphics(pattern)
        self.model3d(pattern)

    def page_connectors(self,schematic):
        connectors=schematic.select('PageConnectors/PageConnector')
        self.integer(len(connectors))
        for connector in connectors:
            self.fields(connector,'boolean','Enabled Selected Connected')
            self.values(connector,'number number',start=1)
            self.fields(connector,'integer','Page BusNumber Number Region Group')
            self.text(connector.values[0])
            self.field(connector,'Locked','boolean')

    def sheet_drawings(self,schematic):
        shapes=schematic.select('Shapes/Shape')
        self.integer(len(shapes))
        for shape in shapes:
            self.fields(shape,'boolean','Enabled Selected')
            from ...model.angles import (quarter_turns)
            self.integer(quarter_turns(shape.scalar('TextAngle'), full_turn=math.tau))
            self.fields(shape,'integer','Type FontSize')
            self.fields(shape,'color','FontColor Color BrushColor')
            self.fields(shape,'integer','FontType Page Group')
            self.field(shape,'PenWidth','number')
            self.field(shape,'FontName','text')
            self.first_text_line(shape)
            self.field(shape,'BitmapIndex','integer')
            self.rows(shape.one('Points_New'),'pt','number number')
            self.fields(shape,'integer','RelatedNet RelatedBus')
            self.fields(shape,'boolean','Locked VectorFont')
            self.fields(shape,'number','FontWidth FontScale')

    def wires(self,owner,*,bus=False):
        lines=owner.one('Lines').children('Line')
        self.integer(len(lines))
        for line in lines:
            self.fields(line,'integer','Connect1 Connect2 ConnectL1 ConnectL2 ConnectB1 ConnectB2 Page ConnectMode1 ConnectMode2')
            self.field(line,'BusNumber' if bus else 'NetNumber','integer')
            self.fields(line,'integer','Region Number')
            if not bus:
                self.field(line,'Hidden','boolean')
            self.rows(line.one('Points'),'pt','number number integer')
            self.field(line,'Selected','boolean')
            self.field(line,'Group','integer')
            if not bus:
                self.field(line,'CanUnhide','boolean')
                self.field(line,'Arrows','integer')

    def connections(self,schematic):
        nets=schematic.select('Nets/Net')
        self.integer(len(nets))
        for net in nets:
            self.field(net,'Enabled','boolean')
            self.boolean(False)
            self.fields(net,'boolean','UniteByName ConnectPinByName')
            self.fields(net,'integer','ActiveLine ActivePoint Number')
            self.integer(-1)
            self.text(net.values[0])
            self.fields(net,'number','Width Clearance')
            self.field(net,'NetClass','integer')
            self.field(net,'Global','boolean')
            self.rows(net.one('Parts'),'pt','integer integer')
            self.wires(net)
            self.fields(net,'boolean','Locked CustomColor')
            self.field(net,'WireColor','color')
        buses=schematic.select('Buses/Bus')
        self.integer(len(buses))
        for bus in buses:
            self.field(bus,'Enabled','boolean')
            self.boolean(False)
            self.fields(bus,'integer','ActiveLine ActivePoint Number Region')
            self.integer(-1)
            self.text(bus.values[0])
            self.rows(bus.one('Nets'),'pt','integer')
            self.wires(bus,bus=True)
            self.field(bus,'Locked','boolean')
            self.rows(bus.one('Numbers'),'pt','integer')
        groups=schematic.select('Groups/Group')
        self.integer(len(groups))
        for group in groups:
            self.fields(group,'boolean','Enabled Selected')
            self.values(group,'integer number number')

    def pages(self,schematic):
        self.integer(len(schematic.select('Pages/Page')))
        for page in schematic.select('Pages/Page'):
            self.fields(page,'number','PageWidth PageHeight FLeft FTop FRight FBottom')
            grids=page.select('TitleBlocks/TitleBlock')
            if len(grids)!=6:
                raise ValueError(f'{page.path}: DCH requires six title grids')
            for grid in grids:
                write_title_block(self,grid)
            self.values(page.one('Zones'),'boolean')
            self.fields(page,'integer','HorzZones VertZones ZoneStandard')
            self.field(page,'ZoneFontName','text')
            self.field(page,'ZoneFontSize','integer')
            self.field(page,'ZoneBorder','boolean')
            self.fields(page,'number','HorzZoneBorder VertZoneBorder')
            for name in ('PageXPos','PageyPos'):
                field=page.one(name)
                self.integer(round(float(field.values[0])))
            self.field(page,'PageScale','number')
            self.field(page,'FontLineWidth','number')
            self.field(page,'PageType','integer')

    def tables(self,schematic):
        tables=schematic.select('Tables/Table')
        self.integer(len(tables))
        for table in tables:
            self.fields(table,'boolean','Enabled Selected')
            self.fields(table,'integer','Layer DefAlign DefFontSize Orientation Group Page')
            self.field(table,'DefFontColor','color')
            self.fields(table,'number','DefCellWidth DefCellHeight X1 Y1 X2 Y2')
            self.fields(table,'text','DefFontName Name')
            self.rows(table.one('ColWidths'),'pt','number')
            self.rows(table.one('RowHeights'),'pt','number')
            cells=table.select('Cells/Cell')
            if len(cells)!=len(table.select('ColWidths/pt'))*len(table.select('RowHeights/pt')):
                raise ValueError(f'{table.path}: table cells do not form a rectangle')
            for cell in cells:
                write_text_content(self,cell)
            self.fields(table,'boolean','Locked DefVectorFont')
            self.fields(table,'number','DefFontWidth DefFontScale')
            self.field(table,'HideBorder','boolean')

    def settings(self,schematic):
        settings=schematic.one('Settings')
        self.field(settings,'GridSize','number')
        self.field(settings,'OriginEnabled','boolean')
        self.field(settings,'clAxis','color')
        self.fields(settings,'integer','BusConnectionFont PinNumberFont')
        self.fields(settings,'boolean','GridEnabled DisplayTitles DisplaySheet BusConNetName BusConNetNumber ShowPinNumbers HidePinNumbers BusConAbove BusConBelow')
        self.fields(settings,'number','BusLineWidth WireLineWidth TableLineWidth TitlesLineWidth NodeSize')
        self.fields(settings,'boolean','UnitsMM UnitsMIL UnitsINCH ERC_PinType ERC_NotConnected ERC_SinglePin ERC_Short')
        self.fields(settings,'text','ERC_VCCTemplate ERC_GNDTemplate')
        self.field(settings,'ERC_PinSuperimpose','boolean')

    def category_types(self, parent, name):
        write_category_types(self, parent, name)

    def early_extensions(self,schematic):
        parts=schematic.select('Components/Part')
        for part in parts:
            self.field(part.one('Pattern/Model3D'),'Units','integer')
            for pin in part.select('Pins/Pin'):
                self.field(pin,'NetName','text')
        for part in parts:
            pattern=part.one('Pattern')
            self.field(pattern,'Mounting','integer')
            self.field(pattern,'Pattern_CategoryName','text')
            self.field(pattern,'Pattern_CategoryIndex','integer')
            self.category_types(pattern,'Pattern_CategoryTypes')
            self.rows(pattern.one('PossibleNames'),'PossibleName','text')
            self.field(part,'Manufacturer','text')
            self.field(part,'Component_CategoryName','text')
            self.field(part,'Component_CategoryIndex','integer')
            self.category_types(part,'Component_CategoryTypes')
        for page in schematic.select('Pages/Page'):
            self.field(page,'PageHiddenId','integer')
        for part in parts:
            self.field(part,'PageHiddenId','integer')

    def cache(self, schematic):
        for slot in schematic.select('CacheLib/Slots/Slot'):
            if not slot.children('Definition'):
                raise ValueError(f'{slot.path}: DCH output requires at least one definition '
                                 'per library slot; add a definition or remove the unused slot')
        codecs = LibraryCodecs(write_parameters, Writer.pads, Writer.pattern_graphics,
                               write_model, Writer.symbol_shapes, definition_text='ModelNote')
        write_library_cache(self, schematic,
                            lambda writer, definition: write_definition(writer, definition, codecs))

    def header(self,document):
        self.buffer.extend(b'\x07DTSCHEM')
        self.integer(self.version)
        scale=document.one('/Scale')
        factor = Decimal(str(scale.values[0]))
        if factor.is_finite():
            sign, digits, exponent = factor.as_tuple()
            factor = Decimal((sign, digits, exponent-2))
        self.number(factor)
        for name in ('Xpos','Ypos'):
            field=document.one('/'+name)
            self.integer(round(float(field.values[0])))
        schematic=document.one('/Schematic')
        self.field(schematic,'PictureCount','integer')
        pages=schematic.select('Pages/Page')
        self.integer(len(pages))
        for page in pages:
            self.text(page.values[0])
            self.field(page,'PageType','integer')
        self.integer(0)  # Obsolete companion-picture count in current output layouts.
        from ..asc.document_projection import (legacy_global_fields)
        legacy = legacy_global_fields(schematic)
        for name in ('ShowText', 'TextAlign', 'ShowText2', 'TextAlign2'):
            self.integer(legacy[name])
        self.field(schematic,'HidePower','boolean')
        self.fields(schematic,'number','OriginX OriginY')
        self.text(legacy['FieldName1'])
        self.text(legacy['FieldName2'])
        self.field(schematic,'PartFontVector','boolean')
        self.fields(schematic,'number','PartFontWidth PartFontScale')
        classes=schematic.select('NetClasses/NetClass')
        self.integer(len(classes))
        for row in classes:
            self.values(row,'text integer number number integer',trailing=5)
        self.integer(len(schematic.select('Components/Part')))


def encode_header(document,*,version=46):
    """Verified prefix through the placed-component array count."""
    writer=Writer(version)
    writer.header(document)
    return bytes(writer.buffer)


def encode_components_prefix(document,*,version=46):
    """Verified prefix through complete placed-component base records."""
    writer=Writer(version)
    writer.header(document)
    for part in document.select('/Schematic/Components/Part'):
        writer.component(part)
    return bytes(writer.buffer)


def encode_base(document,*,version=46,compatibility_changes=None):
    """Verified base sections, preceding the append-only extensions."""
    writer=Writer(version,compatibility_changes=compatibility_changes)
    writer.header(document)
    schematic=document.one('/Schematic')
    for part in schematic.select('Components/Part'):
        writer.component(part)
    writer.page_connectors(schematic)
    writer.sheet_drawings(schematic)
    writer.connections(schematic)
    writer.pages(schematic)
    writer.tables(schematic)
    writer.settings(schematic)
    return bytes(writer.buffer)


@export_diagnostics('dch')
def encode(document,*,version=DCH.default_write_version,context=None,report=None):
    """Encode a fully decoded supported document from named facts only."""
    version = DCH.output_version(version)
    if not document.complete or document.representation != 'schematic':
        raise ValueError('complete shared schematic data is required for DCH output; normalize source views with as_schematic()')
    from ....common.conversion import (info, warn)
    from ..compatibility import (apply_capacity, nondefault_net_ids)
    if document.metadata.get('source_version',version)>version:
        info(report, 'schema-version', 'dch', f'output uses schema {version}; newer fields follow their individual conversion rules')
    from ...model.traversal import (footprints)
    schematic=document.one('/Schematic')
    from ...model.schema import (validate_public_content)
    validate_public_content(document, allow_xml_fields=True)
    scale = document.one('/Scale')
    if len(scale.arguments) != 1 or scale.arguments[0].kind != 'number':
        raise ValueError('schematic Scale requires one numeric percentage value')
    for node in document.root.walk():
        if node is scale:
            continue
        if any(value.unit for value in node.arguments):
            raise ValueError(f'{node.path}: binary fields require unqualified values')
    if version<47:
        fields=nondefault_net_ids(schematic)
        if fields:
            warn(report, 'net-hidden-id', 'dch', 'nondefault Net.HiddenId is omitted by output schema below 47', fields)
    if version<48:
        shapes=[shape for pattern in footprints(schematic) for shape in pattern.select('Shapes/Shape')
                if shape.scalar('PadId',-1)!=-1]
        if shapes:
            warn(report, 'shape-pad-id', 'dch', 'footprint Shape.PadId is omitted by output schema below 48', shapes)
    from .prepare import (prepare)
    document=prepare(document,context=context,report=report)
    from ..revision_adaptation import (prepare_revisions)
    prepare_revisions(document.one('/Schematic'), destination='dch', version=version, report=report)
    apply_capacity(document, destination='dch', report=report)
    choices=getattr(context,'path_variables',None)
    if choices is not None:
        from ..path_variables import (prepare_variable_paths)
        schematic=document.one('/Schematic')
        if context.project_dir is not None:
            schematic.set_field('ProjectDir',context.project_dir)
        prepare_variable_paths(schematic,choices,project_dir=schematic.scalar('ProjectDir',''))
    compatibility_changes=[]
    writer=Writer(version,compatibility_changes=compatibility_changes)
    writer.buffer.extend(encode_base(document,version=version,compatibility_changes=compatibility_changes))
    schematic=document.one('/Schematic')
    writer.early_extensions(schematic)
    writer.cache(schematic)
    from .write_extensions import (common, drawings, project)
    common(writer,document)
    drawings(writer,schematic)
    project(writer,schematic)
    if version>=47:
        for net in schematic.select('Nets/Net'):
            writer.field(net,'HiddenId','integer')
    if version>=48:
        for pattern in footprints(schematic):
            for shape in pattern.select('Shapes/Shape'):
                writer.field(shape,'PadId','integer')
    from .versions import (write_extensions)
    write_extensions(writer, schematic)
    if compatibility_changes:
        info(report, 'dch-compatibility-range', 'dch',
             'earlier normalized drawing coordinates are bounded to the DCH writer range',
             list(dict.fromkeys(compatibility_changes)),
             recoverability='current physical drawing geometry remains authoritative and is written in the modern coordinate fields')
    return bytes(writer.buffer)
