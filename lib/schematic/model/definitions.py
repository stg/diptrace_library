"""Named schematic record definitions, independent of serialized field layout."""
from ...common.schema import Child, Field, Record, MISSING
from ...common.model import Value
from dataclasses import replace
from . import vocabulary as names
from .membership import get_net, set_net, net_number, net_dependencies, net_ordinal
from .simulation import (ARGUMENT_SCHEMAS, ARGUMENT_ITEM, OPTION_SCHEMAS, SIMULATOR, SIGNAL,
                         modernize_arguments)
from .library_records import HOLE, SLOT, DEFINITION
from .collections import definition as collection_definition, DESIGN_LINK
from .auxiliary_records import (LOCAL_GROUP, SCHEMATIC_GROUP, BUS_NET, BUS_NUMBER, UNRESOLVED_MEMBER,
                               UNRESOLVED_KEY, SUPPLIERS, MODEL3D, VECTORS, CACHE)
from .nested_records import (WIRE_POINT, CATEGORY_TYPE, CATALOG_ENTRY as _CATALOG_ENTRY, LIBRARY_PATH, SUBFOLDER,
                             POSSIBLE_NAME, MODEL_LINE, GLOBAL_USER_FIELD, INTERNAL_CONNECTION,
                             QUOTE, PASTE_SEGMENT, TERMINAL, TERMINAL_COUNT, DIFFERENTIAL_PAIR,
                             modernize_classifications)
from .field_groups import (USER_FIELD, COMPONENT_USER_FIELD, marking_definition, tuple_definition,
                           BOUNDS, BORDERS, POINT, TEXT_LINE, COLUMN_WIDTH, ROW_HEIGHT,
                           GRID_FIELDS, TITLE_BLOCK, TITLE_CELL, NET_CLASS, TUPLE_GROUPS)


TEXT_FIELDS = set('''Name RefDes Value BaseName BaseRefDes PartName PartDescriptor
PartString LibPath LibPath_Variable Datasheet Manufacturer ModelString ModelSig
StringNumber NetName FontName DefFontName ZoneFontName MarkingFontName Text
Picture_File Picture_File_Variable ProjectDir ProjectLibs_Name Name_Description
Name_Unique RecoveryCode Pattern_Manufacturer Component_CategoryName
Pattern_CategoryName Model3DFile Model3DFile_Variable PointerText PartNumber
Supplier SourceLocator Currency ERC_VCCTemplate ERC_GNDTemplate ModelNote'''.split())

BOOLEAN_FIELDS = set('''Enabled Selected Connected Locked Inverted SurfacePad
Standard Sided VectorFont DefVectorFont FOrientation HideBorder OriginEnabled
OriginCross OriginCircle RecoveryCode_Generator RecoveryCode_Model AllLayers
LockProperties AllowParts FConnect ShowName Hidden NoConnect HorzFlip VertFlip
ShowOrigin ShowUnits CustomMarkingFont MarkingFontAll ShowPart MarkingGenerated Mirror
NoSearch KeepPins UniteByName ConnectPinByName Global CustomColor CanUnhide
HidePower PartFontVector ProjectLibs_Sorted MainSupplier Picture_Proportions
GridEnabled GridSnap DisplayTitles DisplaySheet BusConNetName BusConNetNumber
ShowPinNumbers HidePinNumbers BusConAbove BusConBelow UnitsMM UnitsMIL UnitsINCH
ERC_PinType ERC_NotConnected ERC_SinglePin ERC_Short ERC_PinSuperimpose
UsePartFontColor ZoneBorder Zones VariableParameter1 VariableParameter2
VariableParameter3 VariableParameter4 VariableParameter5 signal_plotted
signal_visible FontMono NameFontMono DefFontMono PartFontMono PictureFlipped'''.split())

INTEGER_FIELDS = set('''Index Type Orientation Number Number1 Number2 Page Group
PartType ShowNumbers PartNumber HiddenId PageHiddenId FieldIndex1 FieldIndex2
ModelType Component_CategoryIndex Pattern_CategoryIndex Mounting ElectricType
NetNumber BitmapIndex RelatedNet RelatedBus FontType FontColor Color BrushColor
TextHorz TextVert TextAlign TextShow NetClass ActiveLine ActivePoint Region
Connect1 Connect2 ConnectL1 ConnectL2 ConnectB1 ConnectB2 ConnectMode1 ConnectMode2
BusNumber Arrows Layer PadHoleType PadShape PadShape_New PadTerminalCount
PadMask_SegmentSide TopMask_State BotMask_State TopPaste_State BotPaste_State
DisableTopMask DisableBottomMask DisableTopPaste DisableBottomPaste Number_New
PadId Id Units Connected1 Connected2 Object1 Object2 SubObject1 SubObject2 Point1
Point2 PointerMode DefAlign DefFontColor Align HorzZones VertZones ZoneStandard
PageType clAxis NodeMode ProjectLibs_Type
ProjectLibs_Content DesignCache_Count SubfolderIndex OriginCommon OriginCourtyard
PictureCount WireColor PartFontColor'''.split())

NUMBER_FIELDS = set('''X Y X1 Y1 X2 Y2 XD YD Width Height Length Angle OriginX
OriginY Origin_X Origin_Y TextAngle FontSize FontWidth FontScale LineSpacing
NameFontSize NameFontWidth NameFontScale PinNumXShift PinNumYShift PinNameXShift
PinNameYShift PinNameRotate PinNumRotate SignalDelay MarkingFontSize PenWidth
Picture_Width Picture_Height Picture_Transparent PatternOrientation Spacing1
Spacing2 Spacing3 PadAngle PadWidth PadHeight PadWidth_New PadHeight_New PadHole
PadHoleH PadCorner PadShape_X PadShape_Y CustomSwell CustomShrink CustomSwell_New
CustomShrink_New PadMask_Percent PadMask_EdgeGap PadMask_SegmentGap GridSize
PinNumberFont BusConnectionFont PartFontSize NetNameFontSize PartFontWidth
PartFontScale BusLineWidth WireLineWidth TableLineWidth TitlesLineWidth NodeSize
PageWidth PageHeight ZoneFontSize PageXPos PageyPos PageScale FLeft FTop FRight
FBottom ArrowSize ExternalRadius DefCellWidth DefCellHeight DefFontSize
DefFontWidth DefFontScale DefLineSpacing FontLineWidth Clearance HorzZoneBorder VertZoneBorder'''.split())

TUPLE_FIELDS = frozenset(TUPLE_GROUPS)


def fields(vocabulary, *, optional_text=(), optional=(), units=None):
    """Declare scalar fields; child records/collections have separate navigation."""
    result = {}
    for name in vocabulary:
        if name in TUPLE_FIELDS:
            kind = 'tuple'
        elif name in NUMBER_FIELDS:
            kind = 'number'
        elif name in INTEGER_FIELDS:
            kind = 'integer'
        elif name in BOOLEAN_FIELDS:
            kind = 'boolean'
        elif name in TEXT_FIELDS:
            kind = 'text'
        else:
            continue
        font_choice = name == 'FontMono' or name.endswith('FontMono')
        default = False if font_choice else '' if name in optional_text else MISSING
        result[name] = Field(name, kind, required=not font_choice and name not in (*optional_text, *optional),
                             default=default,
                             unit=(units or {}).get(name, ''),
                             members=tuple(tuple_definition(name).fields.values()) if kind == 'tuple' else ())
    return result


def record(name, vocabulary, parameters=(), *, optional_text=(), optional=(), extra=(), units=None):
    declared = fields((*vocabulary, *extra), optional_text=optional_text, optional=optional, units=units)
    if name in ('Pin', 'CachedPin'):
        declared['ShowName'] = Field('ShowName', 'boolean', required=True)
    for key, kind, default in parameters:
        declared[key] = Field(key, kind, required=True, default=default,
                              getter=(lambda node: node._ordinal()) if key == 'Index' else None,
                              ordinal_dependencies=(lambda node: (node,)) if key == 'Index' else None,
                              unit=(units or {}).get(key, 'shared length' if key in ('X', 'Y') else ''))
    return Record(name, declared, tuple(key for key, _, _ in parameters))


NAME = ('Name', 'text', '')
REFERENCE = ('RefDes', 'text', '')
INDEX = ('Index', 'integer', 0)
X = ('X', 'number', 0)
Y = ('Y', 'number', 0)

SOURCE_HEADER = Record('SourceHeader', {
    'Type': Field('Type', 'text', required=True, default='DipTrace-Schematic'),
    'Version': Field('Version', 'integer', required=True, default=46),
}, ('Type', 'Version'), 'Adapter identification retained for inspection; output target is selected separately.')
DOCUMENT = Record('SchematicDocument', {
    'Scale': Field('Scale', 'number', required=True, default=100, unit='percent',
                    description='Current document display scale, with 100 as full scale.'),
    'Xpos': Field('Xpos', 'number', required=True, default=0, unit='shared length',
                   description='Document horizontal viewport position.'),
    'Ypos': Field('Ypos', 'number', required=True, default=0, unit='shared length',
                   description='Document vertical viewport position.'),
}, children={'Source': Child('Source', 'SourceHeader', minimum=1),
             'Schematic': Child('Schematic', 'Schematic', minimum=1)})

PART = record('Part', names.COMPONENT_MODEL_FIELDS, (NAME, REFERENCE),
              optional_text=('Value', 'Manufacturer', 'Datasheet'),
              units={'Angle': 'degrees', **{name: 'shared length' for name in ('X', 'Y', 'Width', 'Height', 'Origin_X', 'Origin_Y')}})
CACHED_PART = record('CachedPart', (*names.CACHED_SYMBOL_FIELDS, 'ModelNote', 'Datasheet'),
                     (NAME, REFERENCE), optional_text=('Value', 'Manufacturer'), optional=('Datasheet',))
CACHED_PART = Record(CACHED_PART.name, {**CACHED_PART.fields,
    'Verification': Field('Verification', 'tuple', required=True, default=(False,)*7,
                           item_kind='boolean', length=7,
                           description='Seven compatibility verification states in their established order.'),
}, CACHED_PART.parameters)
PIN = record('Pin', names.PIN_FIELDS, (INDEX, X, Y), extra=('NameFontMono',))
PIN = Record(PIN.name, {**PIN.fields,
    'Net': Field('Net', 'reference', required=True, nullable=True, getter=get_net, setter=set_net,
                 description='Assigned net identity; None means disconnected.'),
    'NetNumber': Field('NetNumber', 'integer', getter=net_number,
                      reference_dependencies=net_dependencies, ordinal_dependencies=net_ordinal,
                      description='Calculated adapter index; edit Net instead.'),
}, PIN.parameters)
CACHED_PIN = record('CachedPin', names.CACHED_PIN_FIELDS, (INDEX, X, Y),
                    extra=('NameFontMono', 'SignalDelay'), optional=('SignalDelay',))
PATTERN = record('Pattern', names.PATTERN_FIELDS, (NAME,),
                 extra=('Datasheet', 'Sided', 'RefDes'), optional=('Datasheet', 'Sided', 'RefDes'))
PATTERN = Record(PATTERN.name, {**PATTERN.fields, 'PadTerminalCount': TERMINAL_COUNT,
    'PadShape': replace(PATTERN.fields['PadShape'], kind='integer|text',
                        description='Shape code or public XML shape label, including empty text.')}, PATTERN.parameters)
PAD = record('Pad', names.PAD_MODEL_FIELDS, (INDEX, ('StringNumber', 'text', ''), NAME, X, Y))
PAD = Record(PAD.name, {**PAD.fields, 'PadTerminalCount': TERMINAL_COUNT,
    'Id': Field('Id', 'integer', description='Optional persistent public pad key; positional writers generate their own indices.'),
    'PadShape_New': replace(PAD.fields['PadShape_New'], kind='integer|text',
                            description='Current shape code or public XML label, including empty text.')}, PAD.parameters)
PAD_STYLE = record('PadStyle', names.PAD_STYLE_FIELDS, (NAME,))
PAD_STYLE = Record(PAD_STYLE.name, {**PAD_STYLE.fields, 'PadTerminalCount': TERMINAL_COUNT,
    'PadShape': replace(PAD_STYLE.fields['PadShape'], kind='integer|text',
                        description='Shape code or public XML label, including empty text.')}, PAD_STYLE.parameters)
SYMBOL_SHAPE = record('SymbolDrawing', names.SYMBOL_DRAWING_MODEL_FIELDS, (INDEX,), extra=('FontMono',),
                      units={'TextAngle': 'radians', 'PenWidth': 'shared length'})
SHEET_SHAPE = record('SheetDrawing', names.SHEET_DRAWING_MODEL_FIELDS, (INDEX,), extra=('FontMono', 'PictureFlipped'),
                     units={'TextAngle': 'radians', 'PenWidth': 'shared length',
                            'Picture_Width': 'shared length', 'Picture_Height': 'shared length'})
PATTERN_SHAPE = record('PatternDrawing', names.PATTERN_DRAWING_FIELDS, (INDEX,),
                       units={'TextAngle': 'radians', 'Width': 'shared length'})
PAGE = record('Page', names.PAGE_FIELDS, (NAME,), extra=('FontLineWidth',),
               units={name: 'shared length' for name in ('HorzZoneBorder', 'VertZoneBorder')})
NET = record('Net', names.NET_FIELDS, (NAME,), extra=('HiddenId',))
BUS = record('Bus', names.BUS_FIELDS, (NAME,))
NET_LINE = record('Wire', names.LINE_FIELDS)
BUS_LINE = record('BusWire', names.BUS_LINE_FIELDS)
CONNECTOR = record('PageConnector', names.PAGE_CONNECTOR_FIELDS, (NAME, X, Y))
SETTINGS = record('Settings', names.SETTINGS_FIELDS,
                  extra=('PartFontMono', 'NetNameFontSize', 'MarkingFontName'),
                  optional=('GridSnap', 'MarkingFontName', 'PartFontSize', 'PartFontColor', 'UsePartFontColor'))
SCHEMATIC = record('Schematic', names.SCHEMATIC_MODEL_FIELDS,
                   optional=('PartFontVector', 'PartFontWidth', 'PartFontScale'))
SCHEMATIC = replace(SCHEMATIC, fields={**SCHEMATIC.fields,
    'ActiveSheet': Field('ActiveSheet', 'integer',
                         description='Selected page position; a resolved link follows page identity. Absent selection uses the first page on XML output.')})
TABLE = record('Table', names.TABLE_FIELDS, extra=('DefFontMono',))
CELL = Record('Cell', {**fields((*names.CELL_FIELDS, 'FontMono')), **BOUNDS.fields, **GRID_FIELDS},
              BOUNDS.parameters, 'A table cell with authored bounds and derived grid position.')
CONTENT = record('TitleField', (*names.CELL_FIELDS, 'Placement'), (INDEX,), extra=('FontMono',))
DIMENSION = record('Dimension', names.DIMENSION_FIELDS, (INDEX,), extra=('FontMono',))


def _owned(schema, **children):
    return replace(schema, children={**schema.children,
        **{name: Child(name, record) for name, record in children.items()}})


PART = _owned(PART, Component_CategoryTypes='Classifications')
CACHED_PART = _owned(CACHED_PART, Component_CategoryTypes='Classifications')
PATTERN = _owned(PATTERN, Pattern_CategoryTypes='Classifications', PossibleNames='PossibleNames',
                 PadMask_TopSegments='PasteSegments', PadMask_BotSegments='PasteSegments')
PAD = _owned(PAD, PadMask_TopSegments='PasteSegments', PadMask_BotSegments='PasteSegments')
PAD_STYLE = _owned(PAD_STYLE, PadMask_TopSegments='PasteSegments', PadMask_BotSegments='PasteSegments')
SCHEMATIC = _owned(SCHEMATIC, ProjectLibs_Folders='ProjectFolders', ProjectLibs_Libs='ProjectLibraries',
                   DesignCache_Links='DesignCacheLinks')

SCHEMATIC = _owned(SCHEMATIC, Pages='Pages', Components='Components', Nets='Nets', Buses='Buses',
                   PageConnectors='PageConnectors', Shapes='SheetDrawings', Tables='Tables',
                   Groups='SchematicGroups', NetClasses='NetClasses', DifferentialPairs='DifferentialPairs',
                   CacheLib='CacheLibrary', Settings='Settings', ssimulator='Simulator',
                   ShowUserfield_Global='GlobalUserFields')
PART = _owned(PART, Pins='Pins', Shapes='SymbolDrawings', UserFields='ComponentUserFields',
              Pattern='Pattern', ModelBody='ModelBody', Suppliers='Suppliers')
CACHED_PART = _owned(CACHED_PART, Pins='CachedPins', Shapes='SymbolDrawings', UserFields='ComponentUserFields',
                     Groups='LocalGroups', ModelBody='ModelBody', Suppliers='Suppliers')
PATTERN = _owned(PATTERN, Pads='Pads', Shapes='PatternDrawings', Holes='Holes', Dimensions='Dimensions',
                 UserFields='UserFields', Model3D='Model3D', Pattern_Groups='LocalGroups',
                 InternalConnections='InternalConnections', PadPoints='Points')
PAD = _owned(PAD, PadPoints_New='Points')
PAD_STYLE = _owned(PAD_STYLE, PadPoints='Points')
for _name in ('PAD', 'PAD_STYLE', 'PATTERN'):
    _schema = globals()[_name]
    globals()[_name] = replace(_schema, children={**_schema.children,
        'PadTerminal': Child('PadTerminal', 'PadTerminal', maximum=None)})
SYMBOL_SHAPE = _owned(SYMBOL_SHAPE, Points_New='Points', TextLine='TextLines')
SHEET_SHAPE = _owned(SHEET_SHAPE, Points_New='Points', TextLine='TextLines')
PATTERN_SHAPE = _owned(PATTERN_SHAPE, Points_New='Points', TextLine='TextLines')
PAGE = _owned(PAGE, TitleBlocks='TitleBlocks')
NET = _owned(NET, Parts='NetMembers', Lines='Wires')
BUS = _owned(BUS, Nets='BusNets', Numbers='BusNumbers', Lines='BusWires')
NET_LINE = _owned(NET_LINE, Points='WirePoints')
BUS_LINE = _owned(BUS_LINE, Points='WirePoints')
TABLE = _owned(TABLE, Cells='TableCells', ColWidths='ColumnWidths', RowHeights='RowHeights')
CATALOG_CATEGORY = replace(_CATALOG_ENTRY, name='CatalogCategory', children={
    'Type': Child('Type', 'CatalogType', maximum=None)})
CATALOG_TYPE = replace(_CATALOG_ENTRY, name='CatalogType', children={
    'Subtype': Child('Subtype', 'CatalogSubtype', maximum=None)})
CATALOG_SUBTYPE = replace(_CATALOG_ENTRY, name='CatalogSubtype')
TITLE_BLOCK = _owned(TITLE_BLOCK, Cells='TitleCells', Contents='TitleFields',
                     ColWidths='ColumnWidths', RowHeights='RowHeights')
TERMINAL = _owned(TERMINAL, ShapePoints='Points')
SLOT = replace(SLOT, children={'Definition': Child('Definition', 'LibraryDefinition', maximum=None)})
DEFINITION = _owned(DEFINITION, Part='CachedPart', Pattern='Pattern')
SIMULATOR = _owned(SIMULATOR, signals='Signals', **{
    name: schema.name for name, schema in {**ARGUMENT_SCHEMAS, **OPTION_SCHEMAS}.items()})
for _name, _schema in ARGUMENT_SCHEMAS.items():
    ARGUMENT_SCHEMAS[_name] = replace(_schema, children={'Item': Child('Item', 'SimulationItem', maximum=None)})
for _name in ('PIN', 'CACHED_PIN', 'PAD', 'SYMBOL_SHAPE', 'SHEET_SHAPE', 'PATTERN_SHAPE',
              'DIMENSION', 'HOLE', 'INTERNAL_CONNECTION'):
    globals()[_name] = _owned(globals()[_name], UnresolvedKeys='UnresolvedKeys')


def definition(node):
    """Select a record definition by its meaning and ownership, not input format."""
    parent = node.parent
    owner = parent.parent if parent is not None else None
    if not node.kind and parent is None:
        return DOCUMENT
    if node.kind == 'Source' and parent is not None and not parent.kind:
        return SOURCE_HEADER
    schema = collection_definition(node)
    if schema is not None:
        return schema
    if parent is not None:
        if node.kind == 'CacheLib' and parent.kind == 'Schematic':
            return CACHE
        if node.kind == 'Model3D' and parent.kind == 'Pattern':
            return MODEL3D
        if parent.kind == 'Model3D' and node.kind in VECTORS:
            return VECTORS[node.kind]
        if node.kind == 'Suppliers' and parent.kind == 'Part':
            return SUPPLIERS
        if node.kind == 'Group' and parent.kind == 'Groups' and owner is not None and owner.kind == 'Schematic':
            return SCHEMATIC_GROUP
        if node.kind == 'Key' and parent.kind == 'UnresolvedKeys':
            return UNRESOLVED_KEY
        if node.kind == 'Link' and parent.kind == 'DesignCache_Links':
            return DESIGN_LINK
        if node.kind == 'CategoryType' and parent.kind in ('Component_CategoryTypes', 'Pattern_CategoryTypes'):
            return CATEGORY_TYPE
        if node.kind == 'Category' and parent.kind in ('Categories', 'PatternCategories'):
            return CATALOG_CATEGORY
        if node.kind == 'Type' and parent.kind == 'Category':
            return CATALOG_TYPE
        if node.kind == 'Subtype' and parent.kind == 'Type':
            return CATALOG_SUBTYPE
        if node.kind in ('Folder', 'Lib') and parent.kind in ('ProjectLibs_Folders', 'ProjectLibs_Libs'):
            return LIBRARY_PATH
        if node.kind == 'Folder' and parent.kind == 'Subfolders':
            return SUBFOLDER
        if node.kind == 'PossibleName' and parent.kind == 'PossibleNames':
            return POSSIBLE_NAME
        if node.kind == 'Line' and parent.kind == 'ModelBody':
            return MODEL_LINE
        if node.kind == 'Line' and parent.kind == 'Lines' and owner is not None:
            return NET_LINE if owner.kind == 'Net' else BUS_LINE if owner.kind == 'Bus' else None
        if node.kind == 'IntCon' and parent.kind == 'InternalConnections':
            return INTERNAL_CONNECTION
        if node.kind == 'Quote' and parent.kind == 'Prices':
            return QUOTE
        if node.kind == 'PadTerminal' and parent.kind in ('Pad', 'Pattern', 'PadStyle'):
            return TERMINAL
        if node.kind == 'PadStyle' and parent.kind == 'PadStyles':
            return PAD_STYLE
        if node.kind == 'DifferentialPair' and parent.kind == 'DifferentialPairs':
            return DIFFERENTIAL_PAIR
    if node.kind == 'Slot' and parent is not None and parent.kind == 'Slots':
        return SLOT
    if node.kind == 'Definition' and parent is not None and parent.kind == 'Slot':
        return DEFINITION
    if node.kind == 'Hole' and parent is not None and parent.kind == 'Holes':
        return HOLE
    if node.kind == 'ssimulator' and parent is not None and parent.kind == 'Schematic':
        return SIMULATOR
    if parent is not None and parent.kind == 'ssimulator':
        return ARGUMENT_SCHEMAS.get(node.kind) or OPTION_SCHEMAS.get(node.kind)
    if node.kind == 'signal' and parent is not None and parent.kind == 'signals':
        return SIGNAL
    if node.kind == 'Item' and parent is not None and parent.kind in ARGUMENT_SCHEMAS:
        return ARGUMENT_ITEM
    if node.kind == 'Part' and parent is not None:
        return PART if parent.kind == 'Components' else CACHED_PART if parent.kind == 'Definition' else None
    if node.kind == 'Pin' and parent is not None and parent.kind == 'Pins' and owner is not None and owner.kind == 'Part':
        return PIN if owner.parent is not None and owner.parent.kind == 'Components' else CACHED_PIN
    if node.kind == 'Pattern' and parent is not None and parent.kind in ('Part', 'Definition', 'Patterns'):
        return PATTERN
    if node.kind == 'Pad' and parent is not None and parent.kind == 'Pads':
        return PAD
    if node.kind == 'Shape' and parent is not None and parent.kind == 'Shapes':
        if owner is not None:
            return {'Part': SYMBOL_SHAPE, 'Pattern': PATTERN_SHAPE, 'Schematic': SHEET_SHAPE}.get(owner.kind)
    if node.kind == 'UserField' and parent is not None and parent.kind == 'UserFields':
        return COMPONENT_USER_FIELD if owner is not None and owner.kind == 'Part' else USER_FIELD
    if node.kind in TUPLE_FIELDS - {'Edges', 'Placement'} and parent is not None and parent.kind in ('Part', 'Schematic'):
        return marking_definition(node.kind)
    if node.kind == 'TitleBlock' and parent is not None and parent.kind == 'TitleBlocks':
        return TITLE_BLOCK
    if node.kind == 'Cell' and parent is not None and parent.kind == 'Cells' and owner is not None:
        return TITLE_CELL if owner.kind == 'TitleBlock' else CELL if owner.kind == 'Table' else None
    if node.kind == 'Content' and parent is not None and parent.kind == 'Contents':
        return CONTENT
    if node.kind == 'Edges' and parent is not None and parent.kind == 'Cell':
        return BORDERS
    if node.kind == 'Placement' and parent is not None and parent.kind == 'Content':
        return BOUNDS
    if node.kind == 'pt' and parent is not None:
        if parent.kind in ('Groups', 'Pattern_Groups'):
            return LOCAL_GROUP
        if parent.kind == 'Nets' and owner is not None and owner.kind == 'Bus':
            return BUS_NET
        if parent.kind == 'Numbers' and owner is not None and owner.kind == 'Bus':
            return BUS_NUMBER
        if parent.kind == 'Parts' and owner is not None and owner.kind == 'Net':
            from .membership import MEMBER
            return MEMBER if node.schema is MEMBER else UNRESOLVED_MEMBER
        if parent.kind == 'ColWidths':
            return COLUMN_WIDTH
        if parent.kind == 'RowHeights':
            return ROW_HEIGHT
        if parent.kind == 'TextLine':
            return TEXT_LINE
        if parent.kind == 'ShowUserfield_Global':
            return GLOBAL_USER_FIELD
        if parent.kind in ('PadMask_TopSegments', 'PadMask_BotSegments'):
            return PASTE_SEGMENT
        if parent.kind == 'Points' and owner is not None and owner.kind == 'Line':
            return WIRE_POINT
        if parent.kind in ('PadPoints', 'PadPoints_New', 'ShapePoints'):
            return POINT
        if parent.kind == 'Points' and owner is not None and owner.kind == 'Pad':
            return POINT
        if parent.kind == 'Points_New' and owner is not None and owner.kind == 'Shape':
            return POINT
    if node.kind == 'NetClass' and parent is not None and parent.kind == 'NetClasses':
        return NET_CLASS
    if node.kind == 'Page' and parent is not None and parent.kind == 'Pages':
        return PAGE
    if node.kind == 'Net' and parent is not None and parent.kind == 'Nets' and owner is not None and owner.kind == 'Schematic':
        return NET
    if node.kind == 'Bus' and parent is not None and parent.kind == 'Buses':
        return BUS
    if node.kind == 'PageConnector' and parent is not None and parent.kind == 'PageConnectors':
        return CONNECTOR
    if node.kind == 'Dimension' and parent is not None and parent.kind == 'Dimensions':
        return DIMENSION
    return {'Settings': SETTINGS, 'Schematic': SCHEMATIC, 'Table': TABLE}.get(node.kind)


def establish(document):
    if document.representation != 'schematic':
        return
    scale = document.root.child('Scale')
    if scale is not None and len(scale.arguments) == 1 and scale.arguments[0].unit == '%':
        value = scale.arguments[0]
        scale.set_values(Value(value.value, value.kind, source=value.source))
    schematic = document.root.child('Schematic')
    if schematic is not None:
        modernize_arguments(schematic)
        modernize_classifications(schematic)
    establish_records(document.root)


def establish_records(root):
    """Establish named storage only for the supplied record subtree."""
    for node in root.walk(include_self=True):
        schema = definition(node)
        if schema is not None:
            if schema is collection_definition(node):
                node.set_values()
            node.bind_schema(schema)
            if schema.fields.get('PadTerminalCount') is TERMINAL_COUNT:
                count = node.child('PadTerminalCount')
                if count is not None:
                    count.detach()


def has_derived_index(node):
    schema = node.schema
    return bool(schema is not None and schema.parameters and schema.parameters[0] == 'Index'
                and schema.fields['Index'].readonly)


def complete_output_defaults(document):
    """Restore codec-required defaults only on an already detached output view."""
    for node in document.root.walk():
        if node.schema is None:
            continue
        for name, field in node.schema.fields.items():
            if field.default is not MISSING and not field.readonly and node.child(name) is None:
                node.set_field(name, *(field.default if field.kind == 'tuple' else (field.default,)))
