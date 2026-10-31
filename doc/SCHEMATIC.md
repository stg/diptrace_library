# Schematic model reference

Generated from `schematic_schema()`. Use this as a lookup reference; start with the
[getting started](GETTING_STARTED.md), [API reference](API.md) and [model guide](MODEL.md).

Normal DCH, ASC and DCHXML imports share these definitions. Record type names
identify schemas; owned-child names are the names used in paths. Fields hold
values, while children hold records or ordered collections. Tuple members are
named below their field. Reflection returns immutable definitions.

The main hierarchy is `/Schematic/{Pages,Components,Nets,Buses,Shapes,Tables,
PageConnectors,Settings,CacheLib}`. A component owns pins, drawings, user fields
and a footprint. A net owns ordered pin members and wires. The cache owns library
slots and variants; those own symbol and footprint definitions.

Shared lengths use three units per millimetre. Unspecified units and enum
meanings are left unspecified rather than inferred from field names. Descriptions
list established enum meanings; other typed compatibility values remain valid.
Angles retain full turns in the model and are normalized by the destination.

`Required` concerns field presence; absence differs from a present `None`.
A listed default is an adapter/construction fallback, not an implicit read of an
absent field. Constructors also supply initial authoring choices. A dash means
no schema fallback. Calculated fields have no independently stored value.
Assignments to stored fields remain subject to relationship constraints.

Child cardinalities permit incremental construction; writers enforce complete
destination requirements. Collection order determines calculated positions.
In-memory `uid` is not a persistent file key. Resolved links use target identity;
unresolved keys and compatibility values are explicit data until resolved.

For relationship ownership, scope, lifecycle and validation see the
[model guide](MODEL.md#ownership-and-relationships).

## Record index

[Borders](#borders) · [Bounds](#bounds) · [Bus](#bus) · [BusNet](#busnet) · [BusNets](#busnets) · [BusNumber](#busnumber) · [BusNumbers](#busnumbers) · [BusWire](#buswire) · [BusWires](#buswires) · [Buses](#buses) · [CacheLibrary](#cachelibrary) · [CachedPart](#cachedpart) · [CachedPin](#cachedpin) · [CachedPins](#cachedpins) · [CatalogCategory](#catalogcategory) · [CatalogSubtype](#catalogsubtype) · [CatalogType](#catalogtype) · [Categories](#categories) · [CategoryType](#categorytype) · [Cell](#cell) · [Classifications](#classifications) · [ColumnWidth](#columnwidth) · [ColumnWidths](#columnwidths) · [ComponentUserField](#componentuserfield) · [ComponentUserFields](#componentuserfields) · [Components](#components) · [DCTransferFunc](#dctransferfunc) · [DesignCacheLink](#designcachelink) · [DesignCacheLinks](#designcachelinks) · [DifferentialPair](#differentialpair) · [DifferentialPairs](#differentialpairs) · [Digital](#digital) · [Dimension](#dimension) · [Dimensions](#dimensions) · [GlobalMarking](#globalmarking) · [GlobalNamedMarking](#globalnamedmarking) · [GlobalUserField](#globaluserfield) · [GlobalUserFields](#globaluserfields) · [Hole](#hole) · [Holes](#holes) · [InternalConnection](#internalconnection) · [InternalConnections](#internalconnections) · [LibraryDefinition](#librarydefinition) · [LibraryPath](#librarypath) · [LibrarySlot](#libraryslot) · [LibrarySubfolder](#librarysubfolder) · [LocalGroup](#localgroup) · [LocalGroups](#localgroups) · [Marking](#marking) · [Model3D](#model3d) · [ModelBody](#modelbody) · [ModelLine](#modelline) · [ModelOffset](#modeloffset) · [ModelRotate](#modelrotate) · [ModelZoom](#modelzoom) · [NamedMarking](#namedmarking) · [Net](#net) · [NetClass](#netclass) · [NetClasses](#netclasses) · [NetMember](#netmember) · [NetMembers](#netmembers) · [NetNumber](#netnumber) · [Nets](#nets) · [Noise](#noise) · [OptionsAC](#optionsac) · [OptionsDC](#optionsdc) · [OptionsGeneral](#optionsgeneral) · [OptionsTransient](#optionstransient) · [Pad](#pad) · [PadStyle](#padstyle) · [PadStyles](#padstyles) · [PadTerminal](#padterminal) · [Pads](#pads) · [Page](#page) · [PageConnector](#pageconnector) · [PageConnectors](#pageconnectors) · [Pages](#pages) · [Part](#part) · [PasteSegment](#pastesegment) · [PasteSegments](#pastesegments) · [Pattern](#pattern) · [PatternDrawing](#patterndrawing) · [PatternDrawings](#patterndrawings) · [Patterns](#patterns) · [Pin](#pin) · [Pins](#pins) · [Point](#point) · [Points](#points) · [PossibleName](#possiblename) · [PossibleNames](#possiblenames) · [Prices](#prices) · [ProjectFolders](#projectfolders) · [ProjectLibraries](#projectlibraries) · [Quote](#quote) · [RowHeight](#rowheight) · [RowHeights](#rowheights) · [Schematic](#schematic) · [SchematicDocument](#schematicdocument) · [SchematicGroup](#schematicgroup) · [SchematicGroups](#schematicgroups) · [Settings](#settings) · [SheetDrawing](#sheetdrawing) · [SheetDrawings](#sheetdrawings) · [Signals](#signals) · [SimulationItem](#simulationitem) · [SimulationSignal](#simulationsignal) · [Simulator](#simulator) · [Slots](#slots) · [SmallSignalAC](#smallsignalac) · [SourceHeader](#sourceheader) · [Subfolders](#subfolders) · [Suppliers](#suppliers) · [SymbolDrawing](#symboldrawing) · [SymbolDrawings](#symboldrawings) · [Table](#table) · [TableCells](#tablecells) · [Tables](#tables) · [TextLine](#textline) · [TextLines](#textlines) · [TitleBlock](#titleblock) · [TitleBlocks](#titleblocks) · [TitleCell](#titlecell) · [TitleCells](#titlecells) · [TitleField](#titlefield) · [TitleFields](#titlefields) · [Transient](#transient) · [UnresolvedKey](#unresolvedkey) · [UnresolvedKeys](#unresolvedkeys) · [UnresolvedNetMember](#unresolvednetmember) · [UserField](#userfield) · [UserFields](#userfields) · [Wire](#wire) · [WirePoint](#wirepoint) · [WirePoints](#wirepoints) · [Wires](#wires)

## Borders

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| TopLine | boolean | yes | no | `False` | — | stored |
| BottomLine | boolean | yes | no | `False` | — | stored |
| LeftLine | boolean | yes | no | `False` | — | stored |
| RightLine | boolean | yes | no | `False` | — | stored |

## Bounds

Two opposite corners, retaining their authored order.

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| X1 | number | yes | no | `0` | shared length | stored |
| Y1 | number | yes | no | `0` | shared length | stored |
| X2 | number | yes | no | `0` | shared length | stored |
| Y2 | number | yes | no | `0` | shared length | stored |

## Bus

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Enabled | boolean | yes | no | — | — | stored |
| Locked | boolean | yes | no | — | — | stored |
| ActiveLine | integer | yes | no | — | — | stored |
| ActivePoint | integer | yes | no | — | — | stored |
| Number | integer | yes | no | — | — | stored |
| Region | integer | yes | no | — | — | stored |
| Name | text | yes | no | `''` | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| Nets | [BusNets](#busnets) | 0..1 |
| Numbers | [BusNumbers](#busnumbers) | 0..1 |
| Lines | [BusWires](#buswires) | 0..1 |

## BusNet

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| NetIndex | integer | yes | no | `-1` | — | stored; Managed index of a bus member net. |

## BusNets

An ordered collection of BusNet records.

| Child | Record type | Count |
| --- | --- | --- |
| pt | [BusNet](#busnet) | 0..many |

## BusNumber

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Number | integer | yes | no | `0` | — | stored |

## BusNumbers

An ordered collection of BusNumber records.

| Child | Record type | Count |
| --- | --- | --- |
| pt | [BusNumber](#busnumber) | 0..many |

## BusWire

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Connect1 | integer | yes | no | — | — | stored |
| Connect2 | integer | yes | no | — | — | stored |
| ConnectL1 | integer | yes | no | — | — | stored |
| ConnectL2 | integer | yes | no | — | — | stored |
| ConnectB1 | integer | yes | no | — | — | stored |
| ConnectB2 | integer | yes | no | — | — | stored |
| Page | integer | yes | no | — | — | stored |
| ConnectMode1 | integer | yes | no | — | — | stored |
| ConnectMode2 | integer | yes | no | — | — | stored |
| BusNumber | integer | yes | no | — | — | stored |
| Region | integer | yes | no | — | — | stored |
| Number | integer | yes | no | — | — | stored |
| Selected | boolean | yes | no | — | — | stored |
| Group | integer | yes | no | — | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| Points | [WirePoints](#wirepoints) | 0..1 |

## BusWires

An ordered collection of BusWire records.

| Child | Record type | Count |
| --- | --- | --- |
| Line | [BusWire](#buswire) | 0..many |

## Buses

An ordered collection of Bus records.

| Child | Record type | Count |
| --- | --- | --- |
| Bus | [Bus](#bus) | 0..many |

## CacheLibrary

| Child | Record type | Count |
| --- | --- | --- |
| Categories | [Categories](#categories) | 0..1 |
| PatternCategories | [Categories](#categories) | 0..1 |
| Subfolders | [Subfolders](#subfolders) | 0..1 |
| Slots | [Slots](#slots) | 0..1 |
| Patterns | [Patterns](#patterns) | 0..1 |
| PadStyles | [PadStyles](#padstyles) | 0..1 |

## CachedPart

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Enabled | boolean | yes | no | — | — | stored |
| PartType | integer | yes | no | — | — | stored |
| PartName | text | yes | no | — | — | stored |
| ShowNumbers | integer | yes | no | — | — | stored |
| Type | integer | yes | no | — | — | stored |
| Number1 | integer | yes | no | — | — | stored |
| Number2 | integer | yes | no | — | — | stored |
| Width | number | yes | no | — | — | stored |
| Height | number | yes | no | — | — | stored |
| Value | text | no | no | `''` | — | stored |
| LockProperties | boolean | yes | no | — | — | stored |
| Origin_X | number | yes | no | — | — | stored |
| Origin_Y | number | yes | no | — | — | stored |
| ModelType | integer | yes | no | — | — | stored |
| ModelString | text | yes | no | — | — | stored |
| SubfolderIndex | integer | yes | no | — | — | stored |
| Manufacturer | text | no | no | `''` | — | stored |
| Component_CategoryName | text | yes | no | — | — | stored |
| Component_CategoryIndex | integer | yes | no | — | — | stored |
| ModelNote | text | yes | no | — | — | stored |
| Datasheet | text | no | no | — | — | stored |
| Name | text | yes | no | `''` | — | stored |
| RefDes | text | yes | no | `''` | — | stored |
| Verification | tuple | yes | no | `(False, False, False, False, False, False, False)` | — | stored; Seven compatibility verification states in their established order. |
| ↳ items | boolean | — | — | — | — | 7 items |

| Child | Record type | Count |
| --- | --- | --- |
| Component_CategoryTypes | [Classifications](#classifications) | 0..1 |
| Pins | [CachedPins](#cachedpins) | 0..1 |
| Shapes | [SymbolDrawings](#symboldrawings) | 0..1 |
| UserFields | [ComponentUserFields](#componentuserfields) | 0..1 |
| Groups | [LocalGroups](#localgroups) | 0..1 |
| ModelBody | [ModelBody](#modelbody) | 0..1 |
| Suppliers | [Suppliers](#suppliers) | 0..1 |

## CachedPin

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Enabled | boolean | yes | no | — | — | stored |
| Locked | boolean | yes | no | — | — | stored |
| ModelSig | text | yes | no | — | — | stored |
| Type | integer | yes | no | — | — | stored |
| Orientation | integer | yes | no | — | — | stored |
| Number | integer | yes | no | — | — | stored |
| Length | number | yes | no | — | — | stored |
| Name | text | yes | no | — | — | stored |
| StringNumber | text | yes | no | — | — | stored |
| ShowName | boolean | yes | no | — | — | stored |
| PinNumXShift | number | yes | no | — | — | stored |
| PinNumYShift | number | yes | no | — | — | stored |
| PinNameXShift | number | yes | no | — | — | stored |
| PinNameYShift | number | yes | no | — | — | stored |
| ElectricType | integer | yes | no | — | — | stored |
| NameFontSize | number | yes | no | — | — | stored |
| NameFontWidth | number | yes | no | — | — | stored |
| NameFontScale | number | yes | no | — | — | stored |
| Group | integer | yes | no | — | — | stored |
| PinNameRotate | number | yes | no | — | — | stored |
| PinNumRotate | number | yes | no | — | — | stored |
| NameFontMono | boolean | no | no | `False` | — | stored |
| SignalDelay | number | no | no | — | — | stored |
| Index | integer | yes | no | `0` | — | calculated |
| X | number | yes | no | `0` | shared length | stored |
| Y | number | yes | no | `0` | shared length | stored |

| Child | Record type | Count |
| --- | --- | --- |
| UnresolvedKeys | [UnresolvedKeys](#unresolvedkeys) | 0..1 |

## CachedPins

An ordered collection of CachedPin records.

| Child | Record type | Count |
| --- | --- | --- |
| Pin | [CachedPin](#cachedpin) | 0..many |

## CatalogCategory

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Name | text | yes | no | `''` | — | stored |
| Index | integer | yes | no | `-1` | — | stored; Declared catalog key; independent of collection position. |

| Child | Record type | Count |
| --- | --- | --- |
| Type | [CatalogType](#catalogtype) | 0..many |

## CatalogSubtype

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Name | text | yes | no | `''` | — | stored |
| Index | integer | yes | no | `-1` | — | stored; Declared catalog key; independent of collection position. |

## CatalogType

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Name | text | yes | no | `''` | — | stored |
| Index | integer | yes | no | `-1` | — | stored; Declared catalog key; independent of collection position. |

| Child | Record type | Count |
| --- | --- | --- |
| Subtype | [CatalogSubtype](#catalogsubtype) | 0..many |

## Categories

An ordered collection of CatalogCategory records.

| Child | Record type | Count |
| --- | --- | --- |
| Category | [CatalogCategory](#catalogcategory) | 0..many |

## CategoryType

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Type | text | yes | no | `''` | — | stored; Classification type name. |
| SubType | text | yes | no | `''` | — | stored; Classification subtype name. |
| TypeIndex | integer | yes | no | `-1` | — | stored; Declared type key. |
| SubTypeIndex | integer | yes | no | `-1` | — | stored; Declared subtype key. |

## Cell

A table cell with authored bounds and derived grid position.

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| FOrientation | boolean | yes | no | — | — | stored |
| FontSize | number | yes | no | — | — | stored |
| FontType | integer | yes | no | — | — | stored |
| Align | integer | yes | no | — | — | stored |
| FontColor | integer | yes | no | — | — | stored |
| Text | text | yes | no | — | — | stored |
| FontName | text | yes | no | — | — | stored |
| VectorFont | boolean | yes | no | — | — | stored |
| FontWidth | number | yes | no | — | — | stored |
| FontScale | number | yes | no | — | — | stored |
| LineSpacing | number | yes | no | — | — | stored |
| FontMono | boolean | no | no | `False` | — | stored |
| X1 | number | yes | no | `0` | shared length | stored |
| Y1 | number | yes | no | `0` | shared length | stored |
| X2 | number | yes | no | `0` | shared length | stored |
| Y2 | number | yes | no | `0` | shared length | stored |
| Column | integer | no | no | — | — | calculated; Zero-based column in its containing grid. |
| Row | integer | no | no | — | — | calculated; Zero-based row in its containing grid. |

## Classifications

An ordered collection of CategoryType records.

| Child | Record type | Count |
| --- | --- | --- |
| CategoryType | [CategoryType](#categorytype) | 0..many |

## ColumnWidth

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Width | number | yes | no | `0` | shared length | stored |

## ColumnWidths

An ordered collection of ColumnWidth records.

| Child | Record type | Count |
| --- | --- | --- |
| pt | [ColumnWidth](#columnwidth) | 0..many |

## ComponentUserField

Component user text/link and its label display and placement.

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Name | text | yes | no | `''` | — | stored; User-visible field name. |
| Value | text | yes | no | `''` | — | stored; Field text or link. |
| Type | integer | yes | no | `0` | — | stored; 0 Text, 1 Link. |
| Show | integer | yes | no | `0` | — | stored; Display choice: 0 Common, 1 Show, 2 Hide. |
| Align | integer | yes | no | `0` | — | stored; 0 Common, 1 Center, 2 Top, 3 Bottom, 4 Left, 5 Right, 6 Corner, 7 Auto, 8 Position. |
| Horz | integer | yes | no | `0` | — | stored; Horizontal text alignment: 0 Center, 1 Right, -1 or 2 Left. |
| Vert | integer | yes | no | `0` | — | stored; Vertical text alignment: 0 Center, 1 Bottom, -1 or 2 Top. |
| X | number | yes | no | `0` | shared length | stored; Local horizontal offset. |
| Y | number | yes | no | `0` | shared length | stored; Local vertical offset. |
| Angle | number | yes | no | `0` | radians | stored; Local text angle. |

## ComponentUserFields

An ordered collection of ComponentUserField records.

| Child | Record type | Count |
| --- | --- | --- |
| UserField | [ComponentUserField](#componentuserfield) | 0..many |

## Components

An ordered collection of Part records.

| Child | Record type | Count |
| --- | --- | --- |
| Part | [Part](#part) | 0..many |

## DCTransferFunc

Ordered simulator settings; engineering suffixes and expressions remain text.

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| SourceType | text | no | no | — | — | stored; Simulator expression or selection. |
| SourceRefDes | text | no | no | — | — | stored; Simulator expression or selection. |
| StartValue | text | no | no | — | — | stored; Simulator expression or selection. |
| Step | text | no | no | — | — | stored; Simulator expression or selection. |
| StopValue | text | no | no | — | — | stored; Simulator expression or selection. |
| SecondSource | text | no | no | — | — | stored; Simulator expression or selection. |
| SecondSourceType | text | no | no | — | — | stored; Simulator expression or selection. |
| SecondSourceRefDes | text | no | no | — | — | stored; Simulator expression or selection. |
| SecondStartValue | text | no | no | — | — | stored; Simulator expression or selection. |
| SecondStep | text | no | no | — | — | stored; Simulator expression or selection. |
| SecondStopValue | text | no | no | — | — | stored; Simulator expression or selection. |

| Child | Record type | Count |
| --- | --- | --- |
| Item | [SimulationItem](#simulationitem) | 0..many |

## DesignCacheLink

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| SlotIndex | integer | yes | no | `-1` | — | stored; Managed library-slot index in the active prefix; a literal capacity value beyond it. |

## DesignCacheLinks

An ordered collection of DesignCacheLink records.

| Child | Record type | Count |
| --- | --- | --- |
| Link | [DesignCacheLink](#designcachelink) | 0..many |

## DifferentialPair

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Name | text | yes | no | `''` | — | stored |
| Enabled | boolean | yes | no | `True` | — | stored |
| PosNet | integer | yes | no | `-1` | — | stored; Managed positive net index. |
| NegNet | integer | yes | no | `-1` | — | stored; Managed negative net index. |
| NetClass | integer | yes | no | `-1` | — | stored; Managed net-class index. |
| CustomColor | boolean | yes | no | `False` | — | stored |
| WireColor | integer | yes | no | `0` | — | stored |

## DifferentialPairs

An ordered collection of DifferentialPair records.

| Child | Record type | Count |
| --- | --- | --- |
| DifferentialPair | [DifferentialPair](#differentialpair) | 0..many |

## Digital

Ordered simulator settings; engineering suffixes and expressions remain text.

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| StartTime | text | no | no | — | — | stored; Simulator expression or selection. |
| Step | text | no | no | — | — | stored; Simulator expression or selection. |
| StopTime | text | no | no | — | — | stored; Simulator expression or selection. |
| GroupBuses | text | no | no | — | — | stored; Simulator expression or selection. |

| Child | Record type | Count |
| --- | --- | --- |
| Item | [SimulationItem](#simulationitem) | 0..many |

## Dimension

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Enabled | boolean | yes | no | — | — | stored |
| Locked | boolean | yes | no | — | — | stored |
| Type | integer | yes | no | — | — | stored |
| Connected1 | integer | yes | no | — | — | stored |
| Object1 | integer | yes | no | — | — | stored |
| SubObject1 | integer | yes | no | — | — | stored |
| Point1 | integer | yes | no | — | — | stored |
| Connected2 | integer | yes | no | — | — | stored |
| Object2 | integer | yes | no | — | — | stored |
| SubObject2 | integer | yes | no | — | — | stored |
| Point2 | integer | yes | no | — | — | stored |
| Layer | integer | yes | no | — | — | stored |
| X1 | number | yes | no | — | — | stored |
| Y1 | number | yes | no | — | — | stored |
| X2 | number | yes | no | — | — | stored |
| Y2 | number | yes | no | — | — | stored |
| XD | number | yes | no | — | — | stored |
| YD | number | yes | no | — | — | stored |
| ArrowSize | number | yes | no | — | — | stored |
| Units | integer | yes | no | — | — | stored |
| VectorFont | boolean | yes | no | — | — | stored |
| FontName | text | yes | no | — | — | stored |
| FontSize | number | yes | no | — | — | stored |
| FontScale | number | yes | no | — | — | stored |
| FontWidth | number | yes | no | — | — | stored |
| ShowUnits | boolean | yes | no | — | — | stored |
| Angle | number | yes | no | — | — | stored |
| ExternalRadius | number | yes | no | — | — | stored |
| PointerMode | integer | yes | no | — | — | stored |
| PointerText | text | yes | no | — | — | stored |
| Group | integer | yes | no | — | — | stored |
| FontMono | boolean | no | no | `False` | — | stored |
| Index | integer | yes | no | `0` | — | calculated |

| Child | Record type | Count |
| --- | --- | --- |
| UnresolvedKeys | [UnresolvedKeys](#unresolvedkeys) | 0..1 |

## Dimensions

An ordered collection of Dimension records.

| Child | Record type | Count |
| --- | --- | --- |
| Dimension | [Dimension](#dimension) | 0..many |

## GlobalMarking

Default label display and alignment.

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Show | integer | yes | no | `0` | — | stored; Display choice: 0 Common, 1 Show, 2 Hide. |
| Align | integer | yes | no | `0` | — | stored; 0 Common, 1 Center, 2 Top, 3 Bottom, 4 Left, 5 Right, 6 Corner, 7 Auto, 8 Position. |

## GlobalNamedMarking

Default name/reference label display and alignment.

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Show | integer | yes | no | `0` | — | stored; Display choice: 0 Common, 1 Show, 2 Hide. |
| ShowPart | integer | yes | no | `0` | — | stored; Part-name suffix choice: 0 Common, 1 Show, 2 Hide. |
| Align | integer | yes | no | `0` | — | stored; 0 Common, 1 Center, 2 Top, 3 Bottom, 4 Left, 5 Right, 6 Corner, 7 Auto, 8 Position. |

## GlobalUserField

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Name | text | yes | no | `''` | — | stored; Display name. |
| Value | text | yes | no | `''` | — | stored; User-field lookup key. |
| Show | integer | yes | no | `0` | — | stored; Display choice: 0 Common, 1 Show, 2 Hide. |
| Align | integer | yes | no | `0` | — | stored; 0 Common, 1 Center, 2 Top, 3 Bottom, 4 Left, 5 Right, 6 Corner, 7 Auto, 8 Position. |

## GlobalUserFields

An ordered collection of GlobalUserField records.

| Child | Record type | Count |
| --- | --- | --- |
| pt | [GlobalUserField](#globaluserfield) | 0..many |

## Hole

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Enabled | boolean | yes | no | `False` | — | stored |
| Locked | boolean | yes | no | `False` | — | stored |
| X | number | yes | no | `0` | shared length | stored |
| Y | number | yes | no | `0` | shared length | stored |
| Diam | number | yes | no | `0` | shared length | stored; Outer diameter. |
| HoleDiam | number | yes | no | `0` | shared length | stored; Drill diameter. |
| Group | integer | yes | no | `-1` | — | stored; Managed pattern-group index; -1 means no group. |

| Child | Record type | Count |
| --- | --- | --- |
| UnresolvedKeys | [UnresolvedKeys](#unresolvedkeys) | 0..1 |

## Holes

An ordered collection of Hole records.

| Child | Record type | Count |
| --- | --- | --- |
| Hole | [Hole](#hole) | 0..many |

## InternalConnection

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| X | integer | yes | no | `0` | — | stored; First pad index; not a coordinate. |
| Y | integer | yes | no | `0` | — | stored; Second pad index; not a coordinate. |

| Child | Record type | Count |
| --- | --- | --- |
| UnresolvedKeys | [UnresolvedKeys](#unresolvedkeys) | 0..1 |

## InternalConnections

An ordered collection of InternalConnection records.

| Child | Record type | Count |
| --- | --- | --- |
| IntCon | [InternalConnection](#internalconnection) | 0..many |

## LibraryDefinition

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Index | integer | no | no | — | — | calculated; Current zero-based variant position within its library slot. |

| Child | Record type | Count |
| --- | --- | --- |
| Part | [CachedPart](#cachedpart) | 0..1 |
| Pattern | [Pattern](#pattern) | 0..1 |

## LibraryPath

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Path | text | yes | no | `''` | — | stored |
| VariablePath | text | no | no | `''` | — | stored |

## LibrarySlot

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Index | integer | no | no | — | — | calculated; Current zero-based library slot position. |
| LibPath | text | yes | no | `''` | — | stored; Library path associated with this slot. |
| VariablePath | text | no | no | `''` | — | stored |
| Model3DFile_Variable | text | no | no | `''` | — | stored; Model path retained on a slot without a definition. |

| Child | Record type | Count |
| --- | --- | --- |
| Definition | [LibraryDefinition](#librarydefinition) | 0..many |

## LibrarySubfolder

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Name | text | yes | no | `''` | — | stored |

## LocalGroup

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Enabled | boolean | yes | no | `True` | — | stored |
| Id | integer | yes | no | `0` | — | stored; Stored local group code, independent of collection position. |
| X | number | yes | no | `0` | shared length | stored |
| Y | number | yes | no | `0` | shared length | stored |

## LocalGroups

An ordered collection of LocalGroup records.

| Child | Record type | Count |
| --- | --- | --- |
| pt | [LocalGroup](#localgroup) | 0..many |

## Marking

A component label display and local placement.

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Show | integer | yes | no | `0` | — | stored; Display choice: 0 Common, 1 Show, 2 Hide. |
| Align | integer | yes | no | `0` | — | stored; 0 Common, 1 Center, 2 Top, 3 Bottom, 4 Left, 5 Right, 6 Corner, 7 Auto, 8 Position. |
| Horz | integer | yes | no | `0` | — | stored; Horizontal text alignment: 0 Center, 1 Right, -1 or 2 Left. |
| Vert | integer | yes | no | `0` | — | stored; Vertical text alignment: 0 Center, 1 Bottom, -1 or 2 Top. |
| X | number | yes | no | `0` | shared length | stored; Local horizontal offset. |
| Y | number | yes | no | `0` | shared length | stored; Local vertical offset. |
| Angle | number | yes | no | `0` | radians | stored; Local text angle. |

## Model3D

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Model3DFile | text | no | no | `''` | — | stored |
| Model3DFile_Variable | text | no | no | `''` | — | stored |
| Mirror | boolean | no | no | `False` | — | stored |
| NoSearch | boolean | no | no | `False` | — | stored |
| Units | integer | no | no | `0` | — | stored |
| IPC_XOff | number | no | no | `0` | — | stored |
| IPC_YOff | number | no | no | `0` | — | stored |
| AutoHeight | number | no | no | `0` | — | stored |
| AutoColor | integer | no | no | `4934475` | — | stored |
| Type | integer | no | no | `0` | — | stored |
| KeepPins | boolean | no | no | `False` | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| Offset | [ModelOffset](#modeloffset) | 0..1 |
| Rotate | [ModelRotate](#modelrotate) | 0..1 |
| Zoom | [ModelZoom](#modelzoom) | 0..1 |

## ModelBody

An ordered collection of ModelLine records.

| Child | Record type | Count |
| --- | --- | --- |
| Line | [ModelLine](#modelline) | 0..many |

## ModelLine

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Text | text | yes | no | `''` | — | stored |

## ModelOffset

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| X | number | yes | no | `0` | — | stored; Model offset on this axis. |
| Y | number | yes | no | `0` | — | stored; Model offset on this axis. |
| Z | number | yes | no | `0` | — | stored; Model offset on this axis. |

## ModelRotate

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| X | number | yes | no | `0` | — | stored; Model rotate on this axis. |
| Y | number | yes | no | `0` | — | stored; Model rotate on this axis. |
| Z | number | yes | no | `0` | — | stored; Model rotate on this axis. |

## ModelZoom

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| X | number | yes | no | `1` | — | stored; Model zoom on this axis. |
| Y | number | yes | no | `1` | — | stored; Model zoom on this axis. |
| Z | number | yes | no | `1` | — | stored; Model zoom on this axis. |

## NamedMarking

A component name/reference label, including its part suffix choice.

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Show | integer | yes | no | `0` | — | stored; Display choice: 0 Common, 1 Show, 2 Hide. |
| ShowPart | integer | yes | no | `0` | — | stored; Part-name suffix choice: 0 Common, 1 Show, 2 Hide. |
| Align | integer | yes | no | `0` | — | stored; 0 Common, 1 Center, 2 Top, 3 Bottom, 4 Left, 5 Right, 6 Corner, 7 Auto, 8 Position. |
| Horz | integer | yes | no | `0` | — | stored; Horizontal text alignment: 0 Center, 1 Right, -1 or 2 Left. |
| Vert | integer | yes | no | `0` | — | stored; Vertical text alignment: 0 Center, 1 Bottom, -1 or 2 Top. |
| X | number | yes | no | `0` | shared length | stored; Local horizontal offset. |
| Y | number | yes | no | `0` | shared length | stored; Local vertical offset. |
| Angle | number | yes | no | `0` | radians | stored; Local text angle. |

## Net

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Enabled | boolean | yes | no | — | — | stored |
| UniteByName | boolean | yes | no | — | — | stored |
| ConnectPinByName | boolean | yes | no | — | — | stored |
| Locked | boolean | yes | no | — | — | stored |
| ActiveLine | integer | yes | no | — | — | stored |
| ActivePoint | integer | yes | no | — | — | stored |
| Number | integer | yes | no | — | — | stored |
| Width | number | yes | no | — | — | stored |
| Clearance | number | yes | no | — | — | stored |
| NetClass | integer | yes | no | — | — | stored |
| CustomColor | boolean | yes | no | — | — | stored |
| WireColor | integer | yes | no | — | — | stored |
| Global | boolean | yes | no | — | — | stored |
| HiddenId | integer | yes | no | — | — | stored |
| Name | text | yes | no | `''` | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| Parts | [NetMembers](#netmembers) | 0..1 |
| Lines | [Wires](#wires) | 0..1 |

## NetClass

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Name | text | yes | no | `''` | — | stored |
| Type | integer | yes | no | `0` | — | stored; 0 Normal, 1 Differential Pair. |
| Width | number | yes | no | `-1` | shared length | stored; -1 inherits the common width. |
| Clearance | number | yes | no | `-1` | shared length | stored; -1 inherits common clearance. |
| UpdateId | integer | yes | no | `0` | — | stored; Persistent class update identity. |
| DifClearance | number | yes | no | `-1` | shared length | stored |
| MaxUncoupledLength | number | yes | no | `0` | shared length | stored |
| Tolerance | number | yes | no | `0` | shared length | stored |
| Phase | number | yes | no | `0` | shared length | stored |
| Phase_ErrorLength | number | yes | no | `0` | shared length | stored |

## NetClasses

An ordered collection of NetClass records.

| Child | Record type | Count |
| --- | --- | --- |
| NetClass | [NetClass](#netclass) | 0..many |

## NetMember

An ordered pin membership in its containing net.

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Pin | reference | no | no | — | — | calculated; The member pin identity. |
| PartIndex | integer | no | no | — | — | calculated |
| PinIndex | integer | no | no | — | — | calculated |

## NetMembers

An ordered collection of NetMember|UnresolvedNetMember records.

| Child | Record type | Count |
| --- | --- | --- |
| pt | [NetMember](#netmember) or [UnresolvedNetMember](#unresolvednetmember) | 0..many |

## NetNumber

Calculated compatibility view of a pin net.

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Value | integer | no | no | — | — | calculated |

## Nets

An ordered collection of Net records.

| Child | Record type | Count |
| --- | --- | --- |
| Net | [Net](#net) | 0..many |

## Noise

Ordered simulator settings; engineering suffixes and expressions remain text.

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| OutputNet | text | no | no | — | — | stored; Simulator expression or selection. |
| ReferenceNet | text | no | no | — | — | stored; Simulator expression or selection. |
| Source | text | no | no | — | — | stored; Simulator expression or selection. |
| Variation | text | no | no | — | — | stored; Simulator expression or selection. |
| NumberOfPoints | text | no | no | — | — | stored; Simulator expression or selection. |
| StartFrequency | text | no | no | — | — | stored; Simulator expression or selection. |
| StopFrequency | text | no | no | — | — | stored; Simulator expression or selection. |
| PointsPerSummary | text | no | no | — | — | stored; Simulator expression or selection. |

| Child | Record type | Count |
| --- | --- | --- |
| Item | [SimulationItem](#simulationitem) | 0..many |

## OptionsAC

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| NoOPAnalysis | boolean | yes | no | `True` | — | stored |

## OptionsDC

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| AbsCurrentTolerance | text | yes | no | `'1p'` | — | stored |
| MinConductance | text | yes | no | `'1p'` | — | stored |
| ConductanceSteps | integer | yes | no | `25` | — | stored |
| SkipConductanceStepping | boolean | yes | no | `False` | — | stored |
| Iteration | integer | yes | no | `100` | — | stored |
| TransferCurveIteration | integer | yes | no | `50` | — | stored |
| StartFromConductanceStepping | boolean | yes | no | `False` | — | stored |
| PivotRation | text | yes | no | `'1e-3'` | — | stored |
| PivotTolerance | text | yes | no | `'1e-13'` | — | stored |
| RelativeError | text | yes | no | `'1e-3'` | — | stored |
| GroundResistor | text | yes | no | `'1T'` | — | stored |
| VoltageError | text | yes | no | `'1u'` | — | stored |

## OptionsGeneral

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| NoPrintStat | boolean | yes | no | `True` | — | stored |
| NoPrintModelParams | boolean | yes | no | `True` | — | stored |
| Temp | text | yes | no | `'27.0'` | — | stored |
| TempNomMeasure | text | yes | no | `'27.0'` | — | stored |

## OptionsTransient

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| ChargeTolerance | text | yes | no | `'1e-14'` | — | stored |
| LowIteration | integer | yes | no | `4` | — | stored |
| PointIteration | integer | yes | no | `10` | — | stored |
| TotalIteration | integer | yes | no | `5000` | — | stored |
| SourceStepping | integer | yes | no | `25` | — | stored |
| MethodMaxOrder | integer | yes | no | `2` | — | stored |
| Method | integer | yes | no | `1` | — | stored |
| SourceSteppingChange | text | yes | no | `'0'` | — | stored |
| ErrorTolerance | text | yes | no | `'1'` | — | stored |
| TrapezoidalDampingFactor | text | yes | no | `'0.5'` | — | stored |

## Pad

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Number_New | integer | yes | no | — | — | stored |
| Locked | boolean | yes | no | — | — | stored |
| Sided | boolean | yes | no | — | — | stored |
| DisableTopMask | integer | yes | no | — | — | stored |
| DisableBottomMask | integer | yes | no | — | — | stored |
| DisableTopPaste | integer | yes | no | — | — | stored |
| DisableBottomPaste | integer | yes | no | — | — | stored |
| CustomSwell_New | number | yes | no | — | — | stored |
| CustomShrink_New | number | yes | no | — | — | stored |
| PadHole | number | yes | no | — | — | stored |
| PadHoleH | number | yes | no | — | — | stored |
| PadHoleType | integer | yes | no | — | — | stored |
| SurfacePad | boolean | yes | no | — | — | stored |
| PadShape_New | integer | yes | no | — | — | stored; Pad-shape code: 0 ellipse, 1 obround, 2 rectangle, 3 polygon, 4 D-shape, 5 unnamed, 20 fiducial; other numeric codes remain explicit. |
| PadAngle | number | yes | no | — | — | stored |
| PadShape_X | number | yes | no | — | — | stored |
| PadShape_Y | number | yes | no | — | — | stored |
| PadCorner | number | yes | no | — | — | stored |
| PadWidth_New | number | yes | no | — | — | stored |
| PadHeight_New | number | yes | no | — | — | stored |
| Group | integer | yes | no | — | — | stored |
| Standard | boolean | yes | no | — | — | stored |
| PadTerminalCount | integer | no | no | — | — | calculated; Calculated number of current terminal records. |
| PadMask_Percent | number | yes | no | — | — | stored |
| PadMask_EdgeGap | number | yes | no | — | — | stored |
| PadMask_SegmentGap | number | yes | no | — | — | stored |
| PadMask_SegmentSide | number | yes | no | — | shared length | stored |
| Index | integer | yes | no | `0` | — | calculated |
| StringNumber | text | yes | no | `''` | — | stored |
| Name | text | yes | no | `''` | — | stored |
| X | number | yes | no | `0` | shared length | stored |
| Y | number | yes | no | `0` | shared length | stored |
| Id | integer | no | no | — | — | stored; Optional persistent public pad key; positional writers generate their own indices. |

| Child | Record type | Count |
| --- | --- | --- |
| PadMask_TopSegments | [PasteSegments](#pastesegments) | 0..1 |
| PadMask_BotSegments | [PasteSegments](#pastesegments) | 0..1 |
| PadPoints_New | [Points](#points) | 0..1 |
| PadTerminal | [PadTerminal](#padterminal) | 0..many |
| UnresolvedKeys | [UnresolvedKeys](#unresolvedkeys) | 0..1 |

## PadStyle

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| SurfacePad | boolean | yes | no | — | — | stored |
| Sided | boolean | yes | no | — | — | stored |
| PadHoleType | integer | yes | no | — | — | stored |
| PadHole | number | yes | no | — | — | stored |
| PadHoleH | number | yes | no | — | — | stored |
| PadShape | integer | yes | no | — | — | stored; Pad-shape code: 0 ellipse, 1 obround, 2 rectangle, 3 polygon, 4 D-shape, 5 unnamed, 20 fiducial; other numeric codes remain explicit. |
| PadWidth | number | yes | no | — | — | stored |
| PadHeight | number | yes | no | — | — | stored |
| PadCorner | number | yes | no | — | — | stored |
| PadShape_X | number | yes | no | — | — | stored |
| PadShape_Y | number | yes | no | — | — | stored |
| PadTerminalCount | integer | no | no | — | — | calculated; Calculated number of current terminal records. |
| TopMask_State | integer | yes | no | — | — | stored |
| BotMask_State | integer | yes | no | — | — | stored |
| TopPaste_State | integer | yes | no | — | — | stored |
| BotPaste_State | integer | yes | no | — | — | stored |
| CustomSwell_New | number | yes | no | — | — | stored |
| CustomShrink_New | number | yes | no | — | — | stored |
| PadMask_Percent | number | yes | no | — | — | stored |
| PadMask_EdgeGap | number | yes | no | — | — | stored |
| PadMask_SegmentGap | number | yes | no | — | — | stored |
| PadMask_SegmentSide | number | yes | no | — | shared length | stored |
| Name | text | yes | no | `''` | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| PadMask_TopSegments | [PasteSegments](#pastesegments) | 0..1 |
| PadMask_BotSegments | [PasteSegments](#pastesegments) | 0..1 |
| PadPoints | [Points](#points) | 0..1 |
| PadTerminal | [PadTerminal](#padterminal) | 0..many |

## PadStyles

An ordered collection of PadStyle records.

| Child | Record type | Count |
| --- | --- | --- |
| PadStyle | [PadStyle](#padstyle) | 0..many |

## PadTerminal

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Index | integer | no | no | — | — | calculated; Current terminal position. |
| Type | integer\|text | yes | no | `0` | — | stored; Terminal shape code or a public text selection, including empty text. |
| Angle | number | yes | no | `0` | — | stored; Unquantized terminal angle in its public field representation. |
| X | number | yes | no | `0` | shared length | stored |
| Y | number | yes | no | `0` | shared length | stored |
| ShapeWidth | number | yes | no | `0` | shared length | stored |
| ShapeHeight | number | yes | no | `0` | shared length | stored |
| ShapeCorner | number | yes | no | `0` | percent | stored |

| Child | Record type | Count |
| --- | --- | --- |
| ShapePoints | [Points](#points) | 0..1 |

## Pads

An ordered collection of Pad records.

| Child | Record type | Count |
| --- | --- | --- |
| Pad | [Pad](#pad) | 0..many |

## Page

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Zones | boolean | yes | no | — | — | stored |
| PageWidth | number | yes | no | — | — | stored |
| PageHeight | number | yes | no | — | — | stored |
| HorzZones | integer | yes | no | — | — | stored |
| VertZones | integer | yes | no | — | — | stored |
| ZoneStandard | integer | yes | no | — | — | stored |
| ZoneFontName | text | yes | no | — | — | stored |
| ZoneFontSize | number | yes | no | — | — | stored |
| ZoneBorder | boolean | yes | no | — | — | stored |
| HorzZoneBorder | number | yes | no | — | shared length | stored |
| VertZoneBorder | number | yes | no | — | shared length | stored |
| PageXPos | number | yes | no | — | — | stored |
| PageyPos | number | yes | no | — | — | stored |
| PageScale | number | yes | no | — | — | stored |
| PageType | integer | yes | no | — | — | stored |
| PageHiddenId | integer | yes | no | — | — | stored |
| FLeft | number | yes | no | — | — | stored |
| FTop | number | yes | no | — | — | stored |
| FRight | number | yes | no | — | — | stored |
| FBottom | number | yes | no | — | — | stored |
| FontLineWidth | number | yes | no | — | — | stored |
| Name | text | yes | no | `''` | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| TitleBlocks | [TitleBlocks](#titleblocks) | 0..1 |

## PageConnector

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Enabled | boolean | yes | no | — | — | stored |
| Selected | boolean | yes | no | — | — | stored |
| Connected | boolean | yes | no | — | — | stored |
| Page | integer | yes | no | — | — | stored |
| BusNumber | integer | yes | no | — | — | stored |
| Number | integer | yes | no | — | — | stored |
| Region | integer | yes | no | — | — | stored |
| Group | integer | yes | no | — | — | stored |
| Locked | boolean | yes | no | — | — | stored |
| Name | text | yes | no | `''` | — | stored |
| X | number | yes | no | `0` | shared length | stored |
| Y | number | yes | no | `0` | shared length | stored |

## PageConnectors

An ordered collection of PageConnector records.

| Child | Record type | Count |
| --- | --- | --- |
| PageConnector | [PageConnector](#pageconnector) | 0..many |

## Pages

An ordered collection of Page records.

| Child | Record type | Count |
| --- | --- | --- |
| Page | [Page](#page) | 0..many |

## Part

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Enabled | boolean | yes | no | — | — | stored |
| Selected | boolean | yes | no | — | — | stored |
| Value | text | no | no | `''` | — | stored |
| BaseName | text | yes | no | — | — | stored |
| BaseRefDes | text | yes | no | — | — | stored |
| X | number | yes | no | — | shared length | stored |
| Y | number | yes | no | — | shared length | stored |
| Type | integer | yes | no | — | — | stored |
| Number1 | integer | yes | no | — | — | stored |
| Number2 | integer | yes | no | — | — | stored |
| Page | integer | yes | no | — | — | stored |
| Group | integer | yes | no | — | — | stored |
| Number | integer | yes | no | — | — | stored |
| Width | number | yes | no | — | shared length | stored |
| Height | number | yes | no | — | shared length | stored |
| PartNumber | integer | yes | no | — | — | stored |
| PartType | integer | yes | no | — | — | stored |
| PartName | text | yes | no | — | — | stored |
| PartDescriptor | text | yes | no | — | — | stored |
| AllowParts | boolean | yes | no | — | — | stored |
| ShowNumbers | integer | yes | no | — | — | stored |
| PartString | text | yes | no | — | — | stored |
| HiddenId | integer | yes | no | — | — | stored |
| Locked | boolean | yes | no | — | — | stored |
| Angle | number | yes | no | — | degrees | stored |
| LibPath | text | yes | no | — | — | stored |
| LibPath_Variable | text | yes | no | — | — | stored |
| ModelType | integer | yes | no | — | — | stored |
| ModelString | text | yes | no | — | — | stored |
| LockProperties | boolean | yes | no | — | — | stored |
| Origin_X | number | yes | no | — | shared length | stored |
| Origin_Y | number | yes | no | — | shared length | stored |
| Datasheet | text | no | no | `''` | — | stored |
| HorzFlip | boolean | yes | no | — | — | stored |
| VertFlip | boolean | yes | no | — | — | stored |
| ShowOrigin | boolean | yes | no | — | — | stored |
| PageHiddenId | integer | yes | no | — | — | stored |
| Manufacturer | text | no | no | `''` | — | stored |
| Component_CategoryName | text | yes | no | — | — | stored |
| Component_CategoryIndex | integer | yes | no | — | — | stored |
| CustomMarkingFont | boolean | yes | no | — | — | stored |
| MarkingFontSize | number | yes | no | — | — | stored |
| MarkingFontAll | boolean | yes | no | — | — | stored |
| ShowRefDes | tuple | yes | no | — | — | stored |
| ↳ Show | integer | yes | no | 0 | — | Display choice: 0 Common, 1 Show, 2 Hide. |
| ↳ ShowPart | integer | yes | no | 0 | — | Part-name suffix choice: 0 Common, 1 Show, 2 Hide. |
| ↳ Align | integer | yes | no | 0 | — | 0 Common, 1 Center, 2 Top, 3 Bottom, 4 Left, 5 Right, 6 Corner, 7 Auto, 8 Position. |
| ↳ Horz | integer | yes | no | 0 | — | Horizontal text alignment: 0 Center, 1 Right, -1 or 2 Left. |
| ↳ Vert | integer | yes | no | 0 | — | Vertical text alignment: 0 Center, 1 Bottom, -1 or 2 Top. |
| ↳ X | number | yes | no | 0 | shared length | Local horizontal offset. |
| ↳ Y | number | yes | no | 0 | shared length | Local vertical offset. |
| ↳ Angle | number | yes | no | 0 | radians | Local text angle. |
| ShowName | tuple | yes | no | — | — | stored |
| ↳ Show | integer | yes | no | 0 | — | Display choice: 0 Common, 1 Show, 2 Hide. |
| ↳ ShowPart | integer | yes | no | 0 | — | Part-name suffix choice: 0 Common, 1 Show, 2 Hide. |
| ↳ Align | integer | yes | no | 0 | — | 0 Common, 1 Center, 2 Top, 3 Bottom, 4 Left, 5 Right, 6 Corner, 7 Auto, 8 Position. |
| ↳ Horz | integer | yes | no | 0 | — | Horizontal text alignment: 0 Center, 1 Right, -1 or 2 Left. |
| ↳ Vert | integer | yes | no | 0 | — | Vertical text alignment: 0 Center, 1 Bottom, -1 or 2 Top. |
| ↳ X | number | yes | no | 0 | shared length | Local horizontal offset. |
| ↳ Y | number | yes | no | 0 | shared length | Local vertical offset. |
| ↳ Angle | number | yes | no | 0 | radians | Local text angle. |
| ShowValue | tuple | yes | no | — | — | stored |
| ↳ Show | integer | yes | no | 0 | — | Display choice: 0 Common, 1 Show, 2 Hide. |
| ↳ Align | integer | yes | no | 0 | — | 0 Common, 1 Center, 2 Top, 3 Bottom, 4 Left, 5 Right, 6 Corner, 7 Auto, 8 Position. |
| ↳ Horz | integer | yes | no | 0 | — | Horizontal text alignment: 0 Center, 1 Right, -1 or 2 Left. |
| ↳ Vert | integer | yes | no | 0 | — | Vertical text alignment: 0 Center, 1 Bottom, -1 or 2 Top. |
| ↳ X | number | yes | no | 0 | shared length | Local horizontal offset. |
| ↳ Y | number | yes | no | 0 | shared length | Local vertical offset. |
| ↳ Angle | number | yes | no | 0 | radians | Local text angle. |
| ShowManufacturer | tuple | yes | no | — | — | stored |
| ↳ Show | integer | yes | no | 0 | — | Display choice: 0 Common, 1 Show, 2 Hide. |
| ↳ Align | integer | yes | no | 0 | — | 0 Common, 1 Center, 2 Top, 3 Bottom, 4 Left, 5 Right, 6 Corner, 7 Auto, 8 Position. |
| ↳ Horz | integer | yes | no | 0 | — | Horizontal text alignment: 0 Center, 1 Right, -1 or 2 Left. |
| ↳ Vert | integer | yes | no | 0 | — | Vertical text alignment: 0 Center, 1 Bottom, -1 or 2 Top. |
| ↳ X | number | yes | no | 0 | shared length | Local horizontal offset. |
| ↳ Y | number | yes | no | 0 | shared length | Local vertical offset. |
| ↳ Angle | number | yes | no | 0 | radians | Local text angle. |
| ShowDatasheet | tuple | yes | no | — | — | stored |
| ↳ Show | integer | yes | no | 0 | — | Display choice: 0 Common, 1 Show, 2 Hide. |
| ↳ Align | integer | yes | no | 0 | — | 0 Common, 1 Center, 2 Top, 3 Bottom, 4 Left, 5 Right, 6 Corner, 7 Auto, 8 Position. |
| ↳ Horz | integer | yes | no | 0 | — | Horizontal text alignment: 0 Center, 1 Right, -1 or 2 Left. |
| ↳ Vert | integer | yes | no | 0 | — | Vertical text alignment: 0 Center, 1 Bottom, -1 or 2 Top. |
| ↳ X | number | yes | no | 0 | shared length | Local horizontal offset. |
| ↳ Y | number | yes | no | 0 | shared length | Local vertical offset. |
| ↳ Angle | number | yes | no | 0 | radians | Local text angle. |
| Name | text | yes | no | `''` | — | stored |
| RefDes | text | yes | no | `''` | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| Component_CategoryTypes | [Classifications](#classifications) | 0..1 |
| Pins | [Pins](#pins) | 0..1 |
| Shapes | [SymbolDrawings](#symboldrawings) | 0..1 |
| UserFields | [ComponentUserFields](#componentuserfields) | 0..1 |
| Pattern | [Pattern](#pattern) | 0..1 |
| ModelBody | [ModelBody](#modelbody) | 0..1 |
| Suppliers | [Suppliers](#suppliers) | 0..1 |

## PasteSegment

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| X1 | number | yes | no | `0` | shared length | stored |
| Y1 | number | yes | no | `0` | shared length | stored |
| X2 | number | yes | no | `0` | shared length | stored |
| Y2 | number | yes | no | `0` | shared length | stored |

## PasteSegments

An ordered collection of PasteSegment records.

| Child | Record type | Count |
| --- | --- | --- |
| pt | [PasteSegment](#pastesegment) | 0..many |

## Pattern

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Type | integer | yes | no | — | — | stored |
| VariableParameter1 | boolean | yes | no | — | — | stored |
| VariableParameter2 | boolean | yes | no | — | — | stored |
| VariableParameter3 | boolean | yes | no | — | — | stored |
| VariableParameter4 | boolean | yes | no | — | — | stored |
| VariableParameter5 | boolean | yes | no | — | — | stored |
| Number1 | integer | yes | no | — | — | stored |
| Number2 | integer | yes | no | — | — | stored |
| Spacing1 | number | yes | no | — | — | stored |
| Spacing2 | number | yes | no | — | — | stored |
| Spacing3 | number | yes | no | — | — | stored |
| LockProperties | boolean | yes | no | — | — | stored |
| PatternOrientation | number | yes | no | — | — | stored |
| Width | number | yes | no | — | — | stored |
| Height | number | yes | no | — | — | stored |
| OriginCross | boolean | yes | no | — | — | stored |
| OriginCircle | boolean | yes | no | — | — | stored |
| OriginCommon | integer | yes | no | — | — | stored |
| OriginCourtyard | integer | yes | no | — | — | stored |
| Name_Description | text | yes | no | — | — | stored |
| Name_Unique | text | yes | no | — | — | stored |
| RecoveryCode | text | yes | no | — | — | stored |
| RecoveryCode_Generator | boolean | yes | no | — | — | stored |
| RecoveryCode_Model | boolean | yes | no | — | — | stored |
| Pattern_Manufacturer | text | yes | no | — | — | stored |
| PadCorner | number | yes | no | — | — | stored |
| PadShape_X | number | yes | no | — | — | stored |
| PadShape_Y | number | yes | no | — | — | stored |
| PadWidth | number | yes | no | — | — | stored |
| PadHeight | number | yes | no | — | — | stored |
| PadShape | integer | yes | no | — | — | stored; Pad-shape code: 0 ellipse, 1 obround, 2 rectangle, 3 polygon, 4 D-shape, 5 unnamed, 20 fiducial; other numeric codes remain explicit. |
| SurfacePad | boolean | yes | no | — | — | stored |
| PadHole | number | yes | no | — | — | stored |
| PadHoleH | number | yes | no | — | — | stored |
| PadHoleType | integer | yes | no | — | — | stored |
| PadTerminalCount | integer | no | no | — | — | calculated; Calculated number of current terminal records. |
| TopMask_State | integer | yes | no | — | — | stored |
| BotMask_State | integer | yes | no | — | — | stored |
| TopPaste_State | integer | yes | no | — | — | stored |
| BotPaste_State | integer | yes | no | — | — | stored |
| CustomSwell_New | number | yes | no | — | — | stored |
| CustomShrink_New | number | yes | no | — | — | stored |
| PadMask_Percent | number | yes | no | — | — | stored |
| PadMask_EdgeGap | number | yes | no | — | — | stored |
| PadMask_SegmentGap | number | yes | no | — | — | stored |
| PadMask_SegmentSide | number | yes | no | — | shared length | stored |
| OriginX | number | yes | no | — | — | stored |
| OriginY | number | yes | no | — | — | stored |
| Mounting | integer | yes | no | — | — | stored |
| Pattern_CategoryName | text | yes | no | — | — | stored |
| Pattern_CategoryIndex | integer | yes | no | — | — | stored |
| Datasheet | text | no | no | — | — | stored |
| Sided | boolean | no | no | — | — | stored |
| RefDes | text | no | no | — | — | stored |
| Name | text | yes | no | `''` | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| Pattern_CategoryTypes | [Classifications](#classifications) | 0..1 |
| PossibleNames | [PossibleNames](#possiblenames) | 0..1 |
| PadMask_TopSegments | [PasteSegments](#pastesegments) | 0..1 |
| PadMask_BotSegments | [PasteSegments](#pastesegments) | 0..1 |
| Pads | [Pads](#pads) | 0..1 |
| Shapes | [PatternDrawings](#patterndrawings) | 0..1 |
| Holes | [Holes](#holes) | 0..1 |
| Dimensions | [Dimensions](#dimensions) | 0..1 |
| UserFields | [UserFields](#userfields) | 0..1 |
| Model3D | [Model3D](#model3d) | 0..1 |
| Pattern_Groups | [LocalGroups](#localgroups) | 0..1 |
| InternalConnections | [InternalConnections](#internalconnections) | 0..1 |
| PadPoints | [Points](#points) | 0..1 |
| PadTerminal | [PadTerminal](#padterminal) | 0..many |

## PatternDrawing

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Type | integer | yes | no | — | — | stored |
| Locked | boolean | yes | no | — | — | stored |
| Layer | integer | yes | no | — | — | stored |
| FontName | text | yes | no | — | — | stored |
| VectorFont | boolean | yes | no | — | — | stored |
| FontSize | number | yes | no | — | — | stored |
| FontScale | number | yes | no | — | — | stored |
| FontWidth | number | yes | no | — | — | stored |
| FontMono | boolean | no | no | `False` | — | stored |
| TextShow | integer | yes | no | — | — | stored |
| Width | number | yes | no | — | shared length | stored |
| TextAngle | number | yes | no | — | radians | stored |
| TextHorz | integer | yes | no | — | — | stored |
| TextVert | integer | yes | no | — | — | stored |
| TextAlign | integer | yes | no | — | — | stored |
| LineSpacing | number | yes | no | — | — | stored |
| AllLayers | boolean | yes | no | — | — | stored |
| Group | integer | yes | no | — | — | stored |
| PadId | integer | yes | no | — | — | stored |
| Index | integer | yes | no | `0` | — | calculated |

| Child | Record type | Count |
| --- | --- | --- |
| Points_New | [Points](#points) | 0..1 |
| TextLine | [TextLines](#textlines) | 0..1 |
| UnresolvedKeys | [UnresolvedKeys](#unresolvedkeys) | 0..1 |

## PatternDrawings

An ordered collection of PatternDrawing records.

| Child | Record type | Count |
| --- | --- | --- |
| Shape | [PatternDrawing](#patterndrawing) | 0..many |

## Patterns

An ordered collection of Pattern records.

| Child | Record type | Count |
| --- | --- | --- |
| Pattern | [Pattern](#pattern) | 0..many |

## Pin

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Enabled | boolean | yes | no | — | — | stored |
| Type | integer | yes | no | — | — | stored |
| Orientation | integer | yes | no | — | — | stored |
| Number | integer | yes | no | — | — | stored |
| NetNumber | integer | no | no | — | — | calculated; Calculated adapter index; edit Net instead. |
| Length | number | yes | no | — | — | stored |
| Name | text | yes | no | — | — | stored |
| StringNumber | text | yes | no | — | — | stored |
| FConnect | boolean | yes | no | — | — | stored |
| ShowName | boolean | yes | no | — | — | stored |
| PinNumXShift | number | yes | no | — | — | stored |
| PinNumYShift | number | yes | no | — | — | stored |
| PinNameXShift | number | yes | no | — | — | stored |
| PinNameYShift | number | yes | no | — | — | stored |
| ElectricType | integer | yes | no | — | — | stored |
| Hidden | boolean | yes | no | — | — | stored |
| Locked | boolean | yes | no | — | — | stored |
| ModelSig | text | yes | no | — | — | stored |
| NoConnect | boolean | yes | no | — | — | stored |
| NameFontSize | number | yes | no | — | — | stored |
| NameFontWidth | number | yes | no | — | — | stored |
| NameFontScale | number | yes | no | — | — | stored |
| NetName | text | yes | no | — | — | stored |
| SignalDelay | number | yes | no | — | — | stored |
| Group | integer | yes | no | — | — | stored |
| PinNameRotate | number | yes | no | — | — | stored |
| PinNumRotate | number | yes | no | — | — | stored |
| NameFontMono | boolean | no | no | `False` | — | stored |
| Index | integer | yes | no | `0` | — | calculated |
| X | number | yes | no | `0` | shared length | stored |
| Y | number | yes | no | `0` | shared length | stored |
| Net | reference | yes | yes | — | — | relationship; Assigned net identity; None means disconnected. |

| Child | Record type | Count |
| --- | --- | --- |
| UnresolvedKeys | [UnresolvedKeys](#unresolvedkeys) | 0..1 |

## Pins

An ordered collection of Pin records.

| Child | Record type | Count |
| --- | --- | --- |
| Pin | [Pin](#pin) | 0..many |

## Point

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| X | number | yes | no | `0` | shared length | stored |
| Y | number | yes | no | `0` | shared length | stored |

## Points

An ordered collection of Point records.

| Child | Record type | Count |
| --- | --- | --- |
| pt | [Point](#point) | 0..many |

## PossibleName

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Name | text | yes | no | `''` | — | stored |

## PossibleNames

An ordered collection of PossibleName records.

| Child | Record type | Count |
| --- | --- | --- |
| PossibleName | [PossibleName](#possiblename) | 0..many |

## Prices

An ordered collection of Quote records.

| Child | Record type | Count |
| --- | --- | --- |
| Quote | [Quote](#quote) | 0..many |

## ProjectFolders

An ordered collection of LibraryPath records.

| Child | Record type | Count |
| --- | --- | --- |
| Folder | [LibraryPath](#librarypath) | 0..many |

## ProjectLibraries

An ordered collection of LibraryPath records.

| Child | Record type | Count |
| --- | --- | --- |
| Lib | [LibraryPath](#librarypath) | 0..many |

## Quote

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Quantity | integer | yes | no | `0` | — | stored |
| Price | number | yes | no | `0` | — | stored; Unit price in the supplier currency. |

## RowHeight

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Height | number | yes | no | `0` | shared length | stored |

## RowHeights

An ordered collection of RowHeight records.

| Child | Record type | Count |
| --- | --- | --- |
| pt | [RowHeight](#rowheight) | 0..many |

## Schematic

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| PictureCount | integer | yes | no | — | — | stored |
| HidePower | boolean | yes | no | — | — | stored |
| OriginX | number | yes | no | — | — | stored |
| OriginY | number | yes | no | — | — | stored |
| PartFontVector | boolean | no | no | — | — | stored |
| ProjectDir | text | yes | no | — | — | stored |
| PartFontWidth | number | no | no | — | — | stored |
| PartFontScale | number | no | no | — | — | stored |
| ShowRefDes_Global | tuple | yes | no | — | — | stored |
| ↳ Show | integer | yes | no | 0 | — | Display choice: 0 Common, 1 Show, 2 Hide. |
| ↳ ShowPart | integer | yes | no | 0 | — | Part-name suffix choice: 0 Common, 1 Show, 2 Hide. |
| ↳ Align | integer | yes | no | 0 | — | 0 Common, 1 Center, 2 Top, 3 Bottom, 4 Left, 5 Right, 6 Corner, 7 Auto, 8 Position. |
| ShowName_Global | tuple | yes | no | — | — | stored |
| ↳ Show | integer | yes | no | 0 | — | Display choice: 0 Common, 1 Show, 2 Hide. |
| ↳ ShowPart | integer | yes | no | 0 | — | Part-name suffix choice: 0 Common, 1 Show, 2 Hide. |
| ↳ Align | integer | yes | no | 0 | — | 0 Common, 1 Center, 2 Top, 3 Bottom, 4 Left, 5 Right, 6 Corner, 7 Auto, 8 Position. |
| ShowValue_Global | tuple | yes | no | — | — | stored |
| ↳ Show | integer | yes | no | 0 | — | Display choice: 0 Common, 1 Show, 2 Hide. |
| ↳ Align | integer | yes | no | 0 | — | 0 Common, 1 Center, 2 Top, 3 Bottom, 4 Left, 5 Right, 6 Corner, 7 Auto, 8 Position. |
| ShowManufacturer_Global | tuple | yes | no | — | — | stored |
| ↳ Show | integer | yes | no | 0 | — | Display choice: 0 Common, 1 Show, 2 Hide. |
| ↳ Align | integer | yes | no | 0 | — | 0 Common, 1 Center, 2 Top, 3 Bottom, 4 Left, 5 Right, 6 Corner, 7 Auto, 8 Position. |
| ShowDatasheet_Global | tuple | yes | no | — | — | stored |
| ↳ Show | integer | yes | no | 0 | — | Display choice: 0 Common, 1 Show, 2 Hide. |
| ↳ Align | integer | yes | no | 0 | — | 0 Common, 1 Center, 2 Top, 3 Bottom, 4 Left, 5 Right, 6 Corner, 7 Auto, 8 Position. |
| ProjectLibs_Name | text | yes | no | — | — | stored |
| ProjectLibs_Type | integer | yes | no | — | — | stored |
| ProjectLibs_Content | integer | yes | no | — | — | stored |
| ProjectLibs_Sorted | boolean | yes | no | — | — | stored |
| DesignCache_Count | integer | yes | no | — | — | stored |
| ActiveSheet | integer | no | no | — | — | stored; Selected page position; a resolved link follows page identity. Absent selection uses the first page on XML output. |

| Child | Record type | Count |
| --- | --- | --- |
| ProjectLibs_Folders | [ProjectFolders](#projectfolders) | 0..1 |
| ProjectLibs_Libs | [ProjectLibraries](#projectlibraries) | 0..1 |
| DesignCache_Links | [DesignCacheLinks](#designcachelinks) | 0..1 |
| Pages | [Pages](#pages) | 0..1 |
| Components | [Components](#components) | 0..1 |
| Nets | [Nets](#nets) | 0..1 |
| Buses | [Buses](#buses) | 0..1 |
| PageConnectors | [PageConnectors](#pageconnectors) | 0..1 |
| Shapes | [SheetDrawings](#sheetdrawings) | 0..1 |
| Tables | [Tables](#tables) | 0..1 |
| Groups | [SchematicGroups](#schematicgroups) | 0..1 |
| NetClasses | [NetClasses](#netclasses) | 0..1 |
| DifferentialPairs | [DifferentialPairs](#differentialpairs) | 0..1 |
| CacheLib | [CacheLibrary](#cachelibrary) | 0..1 |
| Settings | [Settings](#settings) | 0..1 |
| ssimulator | [Simulator](#simulator) | 0..1 |
| ShowUserfield_Global | [GlobalUserFields](#globaluserfields) | 0..1 |

## SchematicDocument

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Scale | number | yes | no | `100` | percent | stored; Current document display scale, with 100 as full scale. |
| Xpos | number | yes | no | `0` | shared length | stored; Document horizontal viewport position. |
| Ypos | number | yes | no | `0` | shared length | stored; Document vertical viewport position. |

| Child | Record type | Count |
| --- | --- | --- |
| Source | [SourceHeader](#sourceheader) | 1..1 |
| Schematic | [Schematic](#schematic) | 1..1 |

## SchematicGroup

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Index | integer | yes | no | `0` | — | stored; Managed group index. |
| Enabled | boolean | yes | no | `True` | — | stored |
| Selected | boolean | yes | no | `False` | — | stored |
| X | number | yes | no | `0` | shared length | stored |
| Y | number | yes | no | `0` | shared length | stored |

## SchematicGroups

An ordered collection of SchematicGroup records.

| Child | Record type | Count |
| --- | --- | --- |
| Group | [SchematicGroup](#schematicgroup) | 0..many |

## Settings

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| GridSize | number | yes | no | — | — | stored |
| OriginEnabled | boolean | yes | no | — | — | stored |
| clAxis | integer | yes | no | — | — | stored |
| BusConnectionFont | number | yes | no | — | — | stored |
| PinNumberFont | number | yes | no | — | — | stored |
| PartFontSize | number | no | no | — | — | stored |
| PartFontColor | integer | no | no | — | — | stored |
| UsePartFontColor | boolean | no | no | — | — | stored |
| GridEnabled | boolean | yes | no | — | — | stored |
| GridSnap | boolean | no | no | — | — | stored |
| DisplayTitles | boolean | yes | no | — | — | stored |
| DisplaySheet | boolean | yes | no | — | — | stored |
| BusConNetName | boolean | yes | no | — | — | stored |
| BusConNetNumber | boolean | yes | no | — | — | stored |
| ShowPinNumbers | boolean | yes | no | — | — | stored |
| HidePinNumbers | boolean | yes | no | — | — | stored |
| BusConAbove | boolean | yes | no | — | — | stored |
| BusConBelow | boolean | yes | no | — | — | stored |
| BusLineWidth | number | yes | no | — | — | stored |
| WireLineWidth | number | yes | no | — | — | stored |
| TableLineWidth | number | yes | no | — | — | stored |
| TitlesLineWidth | number | yes | no | — | — | stored |
| NodeSize | number | yes | no | — | — | stored |
| UnitsMM | boolean | yes | no | — | — | stored |
| UnitsMIL | boolean | yes | no | — | — | stored |
| UnitsINCH | boolean | yes | no | — | — | stored |
| ERC_PinType | boolean | yes | no | — | — | stored |
| ERC_NotConnected | boolean | yes | no | — | — | stored |
| ERC_SinglePin | boolean | yes | no | — | — | stored |
| ERC_Short | boolean | yes | no | — | — | stored |
| ERC_VCCTemplate | text | yes | no | — | — | stored |
| ERC_GNDTemplate | text | yes | no | — | — | stored |
| ERC_PinSuperimpose | boolean | yes | no | — | — | stored |
| PartFontMono | boolean | no | no | `False` | — | stored |
| NetNameFontSize | number | yes | no | — | — | stored |
| MarkingFontName | text | no | no | — | — | stored |

## SheetDrawing

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Enabled | boolean | yes | no | — | — | stored |
| Selected | boolean | yes | no | — | — | stored |
| Type | integer | yes | no | — | — | stored |
| FontSize | number | yes | no | — | — | stored |
| FontColor | integer | yes | no | — | — | stored |
| Color | integer | yes | no | — | — | stored |
| BrushColor | integer | yes | no | — | — | stored |
| FontType | integer | yes | no | — | — | stored |
| Page | integer | yes | no | — | — | stored |
| Group | integer | yes | no | — | — | stored |
| PenWidth | number | yes | no | — | shared length | stored |
| FontName | text | yes | no | — | — | stored |
| BitmapIndex | integer | yes | no | — | — | stored |
| RelatedNet | integer | yes | no | — | — | stored |
| RelatedBus | integer | yes | no | — | — | stored |
| Locked | boolean | yes | no | — | — | stored |
| VectorFont | boolean | yes | no | — | — | stored |
| FontWidth | number | yes | no | — | — | stored |
| FontScale | number | yes | no | — | — | stored |
| Picture_Width | number | yes | no | — | shared length | stored |
| Picture_Height | number | yes | no | — | shared length | stored |
| Picture_Transparent | number | yes | no | — | — | stored |
| Picture_File | text | yes | no | — | — | stored |
| Picture_File_Variable | text | yes | no | — | — | stored |
| Picture_Proportions | boolean | yes | no | — | — | stored |
| TextHorz | integer | yes | no | — | — | stored |
| TextVert | integer | yes | no | — | — | stored |
| TextAlign | integer | yes | no | — | — | stored |
| TextAngle | number | yes | no | — | radians | stored |
| LineSpacing | number | yes | no | — | — | stored |
| FontMono | boolean | no | no | `False` | — | stored |
| PictureFlipped | boolean | yes | no | — | — | stored |
| Index | integer | yes | no | `0` | — | calculated |

| Child | Record type | Count |
| --- | --- | --- |
| Points_New | [Points](#points) | 0..1 |
| TextLine | [TextLines](#textlines) | 0..1 |
| UnresolvedKeys | [UnresolvedKeys](#unresolvedkeys) | 0..1 |

## SheetDrawings

An ordered collection of SheetDrawing records.

| Child | Record type | Count |
| --- | --- | --- |
| Shape | [SheetDrawing](#sheetdrawing) | 0..many |

## Signals

An ordered collection of SimulationSignal records.

| Child | Record type | Count |
| --- | --- | --- |
| signal | [SimulationSignal](#simulationsignal) | 0..many |

## SimulationItem

An additional simulator argument with no established public field name.

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Value | text | yes | no | — | — | stored |

## SimulationSignal

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| signal_tp | integer | yes | no | — | — | stored |
| signal_num | integer | yes | no | — | — | stored |
| signal_display_name | text | yes | no | — | — | stored |
| signal_plotted | boolean | yes | no | — | — | stored |
| signal_visible | boolean | yes | no | — | — | stored |
| signal_color | integer | yes | no | — | — | stored |

## Simulator

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| tp | integer | yes | no | `0` | — | stored; Simulation type code. |
| gndnum | integer | yes | no | `-1` | — | stored; Managed ground-net index; -1 means no ground net. |
| gndname | text | yes | no | `''` | — | stored; Ground net display name. |

| Child | Record type | Count |
| --- | --- | --- |
| signals | [Signals](#signals) | 0..1 |
| sim_ac | [SmallSignalAC](#smallsignalac) | 0..1 |
| sim_dc | [DCTransferFunc](#dctransferfunc) | 0..1 |
| sim_tran | [Transient](#transient) | 0..1 |
| sim_noise | [Noise](#noise) | 0..1 |
| sim_digital | [Digital](#digital) | 0..1 |
| OptionsGeneral | [OptionsGeneral](#optionsgeneral) | 0..1 |
| OptionsDC | [OptionsDC](#optionsdc) | 0..1 |
| OptionsAC | [OptionsAC](#optionsac) | 0..1 |
| OptionsTransient | [OptionsTransient](#optionstransient) | 0..1 |

## Slots

An ordered collection of LibrarySlot records.

| Child | Record type | Count |
| --- | --- | --- |
| Slot | [LibrarySlot](#libraryslot) | 0..many |

## SmallSignalAC

Ordered simulator settings; engineering suffixes and expressions remain text.

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Variation | text | no | no | — | — | stored; Simulator expression or selection. |
| NumberOfPoints | text | no | no | — | — | stored; Simulator expression or selection. |
| StartFrequency | text | no | no | — | — | stored; Simulator expression or selection. |
| StopFrequency | text | no | no | — | — | stored; Simulator expression or selection. |

| Child | Record type | Count |
| --- | --- | --- |
| Item | [SimulationItem](#simulationitem) | 0..many |

## SourceHeader

Adapter identification retained for inspection; output target is selected separately.

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Type | text | yes | no | `'DipTrace-Schematic'` | — | stored |
| Version | integer | yes | no | `46` | — | stored |

## Subfolders

An ordered collection of LibrarySubfolder records.

| Child | Record type | Count |
| --- | --- | --- |
| Folder | [LibrarySubfolder](#librarysubfolder) | 0..many |

## Suppliers

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| PartNumber | text | no | no | `''` | — | stored |
| Manufacturer | text | no | no | `''` | — | stored |
| Pattern | text | no | no | `''` | — | stored |
| Supplier | text | no | no | `''` | — | stored |
| SourceLocator | text | no | no | `''` | — | stored |
| Currency | text | no | no | `''` | — | stored |
| MainSupplier | boolean | no | no | — | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| Prices | [Prices](#prices) | 0..1 |

## SymbolDrawing

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Enabled | boolean | yes | no | — | — | stored |
| Type | integer | yes | no | — | — | stored |
| FontSize | number | yes | no | — | — | stored |
| FontColor | integer | yes | no | — | — | stored |
| FontType | integer | yes | no | — | — | stored |
| FontName | text | yes | no | — | — | stored |
| PenWidth | number | yes | no | — | shared length | stored |
| TextAngle | number | yes | no | — | radians | stored |
| TextHorz | integer | yes | no | — | — | stored |
| TextVert | integer | yes | no | — | — | stored |
| TextAlign | integer | yes | no | — | — | stored |
| LineSpacing | number | yes | no | — | — | stored |
| Group | integer | yes | no | — | — | stored |
| ShowPart | boolean | yes | no | — | — | stored |
| MarkingGenerated | boolean | yes | no | — | — | stored |
| Locked | boolean | yes | no | — | — | stored |
| VectorFont | boolean | yes | no | — | — | stored |
| FontWidth | number | yes | no | — | — | stored |
| FontScale | number | yes | no | — | — | stored |
| FontMono | boolean | no | no | `False` | — | stored |
| Index | integer | yes | no | `0` | — | calculated |

| Child | Record type | Count |
| --- | --- | --- |
| Points_New | [Points](#points) | 0..1 |
| TextLine | [TextLines](#textlines) | 0..1 |
| UnresolvedKeys | [UnresolvedKeys](#unresolvedkeys) | 0..1 |

## SymbolDrawings

An ordered collection of SymbolDrawing records.

| Child | Record type | Count |
| --- | --- | --- |
| Shape | [SymbolDrawing](#symboldrawing) | 0..many |

## Table

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Enabled | boolean | yes | no | — | — | stored |
| Selected | boolean | yes | no | — | — | stored |
| Locked | boolean | yes | no | — | — | stored |
| DefVectorFont | boolean | yes | no | — | — | stored |
| DefFontWidth | number | yes | no | — | — | stored |
| DefFontScale | number | yes | no | — | — | stored |
| HideBorder | boolean | yes | no | — | — | stored |
| Layer | integer | yes | no | — | — | stored |
| DefAlign | integer | yes | no | — | — | stored |
| DefFontSize | number | yes | no | — | — | stored |
| Orientation | integer | yes | no | — | — | stored |
| Group | integer | yes | no | — | — | stored |
| DefFontColor | integer | yes | no | — | — | stored |
| DefCellWidth | number | yes | no | — | — | stored |
| DefCellHeight | number | yes | no | — | — | stored |
| X1 | number | yes | no | — | — | stored |
| Y1 | number | yes | no | — | — | stored |
| X2 | number | yes | no | — | — | stored |
| Y2 | number | yes | no | — | — | stored |
| DefFontName | text | yes | no | — | — | stored |
| Name | text | yes | no | — | — | stored |
| Page | integer | yes | no | — | — | stored |
| DefLineSpacing | number | yes | no | — | — | stored |
| DefFontMono | boolean | no | no | `False` | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| Cells | [TableCells](#tablecells) | 0..1 |
| ColWidths | [ColumnWidths](#columnwidths) | 0..1 |
| RowHeights | [RowHeights](#rowheights) | 0..1 |

## TableCells

An ordered collection of Cell records.

| Child | Record type | Count |
| --- | --- | --- |
| Cell | [Cell](#cell) | 0..many |

## Tables

An ordered collection of Table records.

| Child | Record type | Count |
| --- | --- | --- |
| Table | [Table](#table) | 0..many |

## TextLine

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Text | text | yes | no | `''` | — | stored; Literal text, or calculated content while bound to a component field. |

## TextLines

An ordered collection of TextLine records.

| Child | Record type | Count |
| --- | --- | --- |
| pt | [TextLine](#textline) | 0..many |

## TitleBlock

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Position | integer | no | no | — | — | calculated; 0 BottomRight, 1 BottomLeft, 2 TopRight, 3 TopLeft, 4 ExtTopLeft, 5 ExtBottomLeft. |
| Name | text | yes | no | `''` | — | stored |
| Width | number | yes | no | `0` | shared length | stored |
| Height | number | yes | no | `0` | shared length | stored |

| Child | Record type | Count |
| --- | --- | --- |
| Cells | [TitleCells](#titlecells) | 0..1 |
| Contents | [TitleFields](#titlefields) | 0..1 |
| ColWidths | [ColumnWidths](#columnwidths) | 0..1 |
| RowHeights | [RowHeights](#rowheights) | 0..1 |

## TitleBlocks

| Child | Record type | Count |
| --- | --- | --- |
| TitleBlock | [TitleBlock](#titleblock) | 0..6 |

## TitleCell

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Column | integer | no | no | — | — | calculated; Zero-based column in its containing grid. |
| Row | integer | no | no | — | — | calculated; Zero-based row in its containing grid. |
| FieldId | integer | yes | no | `-1` | — | stored; Field identity projection; -1 means no content. |
| Edges | tuple | yes | no | — | — | stored |
| ↳ TopLine | boolean | yes | no | False | — |  |
| ↳ BottomLine | boolean | yes | no | False | — |  |
| ↳ LeftLine | boolean | yes | no | False | — |  |
| ↳ RightLine | boolean | yes | no | False | — |  |

## TitleCells

An ordered collection of TitleCell records.

| Child | Record type | Count |
| --- | --- | --- |
| Cell | [TitleCell](#titlecell) | 0..many |

## TitleField

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| FOrientation | boolean | yes | no | — | — | stored |
| FontSize | number | yes | no | — | — | stored |
| FontType | integer | yes | no | — | — | stored |
| Align | integer | yes | no | — | — | stored |
| FontColor | integer | yes | no | — | — | stored |
| Text | text | yes | no | — | — | stored |
| FontName | text | yes | no | — | — | stored |
| VectorFont | boolean | yes | no | — | — | stored |
| FontWidth | number | yes | no | — | — | stored |
| FontScale | number | yes | no | — | — | stored |
| LineSpacing | number | yes | no | — | — | stored |
| Placement | tuple | yes | no | — | — | stored |
| ↳ X1 | number | yes | no | 0 | shared length |  |
| ↳ Y1 | number | yes | no | 0 | shared length |  |
| ↳ X2 | number | yes | no | 0 | shared length |  |
| ↳ Y2 | number | yes | no | 0 | shared length |  |
| FontMono | boolean | no | no | `False` | — | stored |
| Index | integer | yes | no | `0` | — | calculated |

## TitleFields

An ordered collection of TitleField records.

| Child | Record type | Count |
| --- | --- | --- |
| Content | [TitleField](#titlefield) | 0..many |

## Transient

Ordered simulator settings; engineering suffixes and expressions remain text.

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| StartTime | text | no | no | — | — | stored; Simulator expression or selection. |
| Step | text | no | no | — | — | stored; Simulator expression or selection. |
| StopTime | text | no | no | — | — | stored; Simulator expression or selection. |

| Child | Record type | Count |
| --- | --- | --- |
| Item | [SimulationItem](#simulationitem) | 0..many |

## UnresolvedKey

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Field | text | yes | no | `''` | — | stored; Name of the unresolved relationship field. |
| Id | integer | yes | no | `0` | — | stored; Unresolved public target key. |

## UnresolvedKeys

An ordered collection of UnresolvedKey records.

| Child | Record type | Count |
| --- | --- | --- |
| Key | [UnresolvedKey](#unresolvedkey) | 0..many |

## UnresolvedNetMember

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| PartIndex | integer | yes | no | `-1` | — | stored |
| PinIndex | integer | yes | no | `-1` | — | stored |

## UserField

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Name | text | yes | no | `''` | — | stored; User-visible field name. |
| Value | text | yes | no | `''` | — | stored; Field text or link. |
| Type | integer | yes | no | `0` | — | stored; 0 Text, 1 Link. |

## UserFields

An ordered collection of UserField records.

| Child | Record type | Count |
| --- | --- | --- |
| UserField | [UserField](#userfield) | 0..many |

## Wire

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Connect1 | integer | yes | no | — | — | stored |
| Connect2 | integer | yes | no | — | — | stored |
| ConnectL1 | integer | yes | no | — | — | stored |
| ConnectL2 | integer | yes | no | — | — | stored |
| ConnectB1 | integer | yes | no | — | — | stored |
| ConnectB2 | integer | yes | no | — | — | stored |
| Page | integer | yes | no | — | — | stored |
| ConnectMode1 | integer | yes | no | — | — | stored |
| ConnectMode2 | integer | yes | no | — | — | stored |
| NetNumber | integer | yes | no | — | — | stored |
| Region | integer | yes | no | — | — | stored |
| Number | integer | yes | no | — | — | stored |
| Hidden | boolean | yes | no | — | — | stored |
| Selected | boolean | yes | no | — | — | stored |
| Group | integer | yes | no | — | — | stored |
| CanUnhide | boolean | yes | no | — | — | stored |
| Arrows | integer | yes | no | — | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| Points | [WirePoints](#wirepoints) | 0..1 |

## WirePoint

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| X | number | yes | no | `0` | shared length | stored |
| Y | number | yes | no | `0` | shared length | stored |
| Dir | integer | yes | no | `0` | — | stored; Stored wire/bus routing direction code. |

## WirePoints

An ordered collection of WirePoint records.

| Child | Record type | Count |
| --- | --- | --- |
| pt | [WirePoint](#wirepoint) | 0..many |

## Wires

An ordered collection of Wire records.

| Child | Record type | Count |
| --- | --- | --- |
| Line | [Wire](#wire) | 0..many |
