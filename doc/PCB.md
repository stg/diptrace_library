# PCB model reference

Generated from `pcb_schema()`. Use this as a lookup reference; start with the
[getting started](GETTING_STARTED.md), [API reference](API.md) and [model guide](MODEL.md).

Normal DIP, PCB ASC and DIPXML imports share these definitions. Record type names
identify schemas; owned-child names are the names used in paths. Fields hold
values, while children hold records or ordered collections. Tuple members are
named below their field. Reflection returns immutable definitions.

The main hierarchy is `/Board/{Components,Nets,NetClasses,DifferentialPairs,
CopperPours,Shapes,Tables,Groups,Layers,CacheLib}`. Components own their physical
patterns and pads; nets own pad membership and routed traces. The cache owns
unplaced symbol and footprint definitions. Layer, class and pad selections use
managed identities.

Supplied pour fill and check results remain editable data. Editing a boundary
does not calculate fill, and editing geometry does not rerun checks or routing.

Shared lengths use three units per millimetre. Unspecified units and enum
meanings are left unspecified rather than inferred from field names. Descriptions
list established enum meanings; other typed compatibility values remain valid.
Component Angle uses radians. Other angle domains remain separate; PCB placement
does not use the schematic quarter-turn rule.

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

[BlindPadLayers](#blindpadlayers) · [Board](#board) · [Borders](#borders) · [Bounds](#bounds) · [CacheLibrary](#cachelibrary) · [CachedPart](#cachedpart) · [CatalogCategory](#catalogcategory) · [CatalogSubtype](#catalogsubtype) · [CatalogType](#catalogtype) · [Categories](#categories) · [CategoryType](#categorytype) · [Cell](#cell) · [Classifications](#classifications) · [ColumnWidth](#columnwidth) · [ColumnWidths](#columnwidths) · [ComponentUserField](#componentuserfield) · [ComponentUserFields](#componentuserfields) · [DesignCacheLink](#designcachelink) · [DesignCacheLinks](#designcachelinks) · [HiddenPadLayers](#hiddenpadlayers) · [Hole](#hole) · [LibraryDefinition](#librarydefinition) · [LibraryDimension](#librarydimension) · [LibraryDimensions](#librarydimensions) · [LibraryHole](#libraryhole) · [LibraryHoles](#libraryholes) · [LibraryInternalConnections](#libraryinternalconnections) · [LibraryPad](#librarypad) · [LibraryPads](#librarypads) · [LibraryPath](#librarypath) · [LibraryPatternDrawing](#librarypatterndrawing) · [LibraryPatternDrawings](#librarypatterndrawings) · [LibraryPin](#librarypin) · [LibraryPins](#librarypins) · [LibrarySlot](#libraryslot) · [LibrarySubfolder](#librarysubfolder) · [LibrarySymbolDrawing](#librarysymboldrawing) · [LibrarySymbolDrawings](#librarysymboldrawings) · [Model3D](#model3d) · [ModelBody](#modelbody) · [ModelLine](#modelline) · [ModelOffset](#modeloffset) · [ModelRotate](#modelrotate) · [ModelZoom](#modelzoom) · [PadStyle](#padstyle) · [PadStyles](#padstyles) · [PadTerminal](#padterminal) · [PadThermals](#padthermals) · [PasteSegment](#pastesegment) · [PasteSegments](#pastesegments) · [Pattern](#pattern) · [Patterns](#patterns) · [PcbAllowedVia](#pcballowedvia) · [PcbAllowedVias](#pcballowedvias) · [PcbAssemblyExclusion](#pcbassemblyexclusion) · [PcbAssemblyExclusions](#pcbassemblyexclusions) · [PcbAssemblyVariant](#pcbassemblyvariant) · [PcbAssemblyVariants](#pcbassemblyvariants) · [PcbBoardDrawing](#pcbboarddrawing) · [PcbBoardDrawings](#pcbboarddrawings) · [PcbBorderZones](#pcbborderzones) · [PcbClassClearance](#pcbclassclearance) · [PcbClassClearanceDetails](#pcbclassclearancedetails) · [PcbClassClearances](#pcbclassclearances) · [PcbClassLayerProperties](#pcbclasslayerproperties) · [PcbClassLayerProperty](#pcbclasslayerproperty) · [PcbClassLengthResults](#pcbclasslengthresults) · [PcbComponent](#pcbcomponent) · [PcbComponents](#pcbcomponents) · [PcbConnectivityCheck](#pcbconnectivitycheck) · [PcbCopperLayer](#pcbcopperlayer) · [PcbCopperLayers](#pcbcopperlayers) · [PcbCopperPour](#pcbcopperpour) · [PcbCopperPours](#pcbcopperpours) · [PcbDesignError](#pcbdesignerror) · [PcbDesignErrors](#pcbdesignerrors) · [PcbDesignRules](#pcbdesignrules) · [PcbDifferentialPair](#pcbdifferentialpair) · [PcbDifferentialPairs](#pcbdifferentialpairs) · [PcbDimension](#pcbdimension) · [PcbDimensions](#pcbdimensions) · [PcbDocument](#pcbdocument) · [PcbDrcClearanceDetails](#pcbdrcclearancedetails) · [PcbDrcLayerClearance](#pcbdrclayerclearance) · [PcbDrcLayerClearances](#pcbdrclayerclearances) · [PcbDrcLayerSize](#pcbdrclayersize) · [PcbDrcLayerSizes](#pcbdrclayersizes) · [PcbErrorLayer](#pcberrorlayer) · [PcbErrorLayers](#pcberrorlayers) · [PcbFillLine](#pcbfillline) · [PcbFillLines](#pcbfilllines) · [PcbFillPolygon](#pcbfillpolygon) · [PcbFillPolygons](#pcbfillpolygons) · [PcbGlobalUserField](#pcbglobaluserfield) · [PcbGlobalUserFields](#pcbglobaluserfields) · [PcbGroup](#pcbgroup) · [PcbGroups](#pcbgroups) · [PcbHoles](#pcbholes) · [PcbInternalConnectionDefinition](#pcbinternalconnectiondefinition) · [PcbInternalConnectionDefinitions](#pcbinternalconnectiondefinitions) · [PcbInternalConnectionPolicies](#pcbinternalconnectionpolicies) · [PcbInternalConnectionPolicy](#pcbinternalconnectionpolicy) · [PcbLayerClearance](#pcblayerclearance) · [PcbLayerClearances](#pcblayerclearances) · [PcbLayerMaterial](#pcblayermaterial) · [PcbLayerPanel](#pcblayerpanel) · [PcbLayerStackItem](#pcblayerstackitem) · [PcbLayerStackItems](#pcblayerstackitems) · [PcbLengthConnection](#pcblengthconnection) · [PcbLengthConnections](#pcblengthconnections) · [PcbLengthRule](#pcblengthrule) · [PcbLengthRules](#pcblengthrules) · [PcbLocalGroup](#pcblocalgroup) · [PcbLocalGroups](#pcblocalgroups) · [PcbNegativePoints](#pcbnegativepoints) · [PcbNegativeTraces](#pcbnegativetraces) · [PcbNet](#pcbnet) · [PcbNetClass](#pcbnetclass) · [PcbNetClasses](#pcbnetclasses) · [PcbNetMember](#pcbnetmember) · [PcbNetMembers](#pcbnetmembers) · [PcbNets](#pcbnets) · [PcbNonSignalLayer](#pcbnonsignallayer) · [PcbNonSignalLayers](#pcbnonsignallayers) · [PcbOutlinePoint](#pcboutlinepoint) · [PcbOutlinePoints](#pcboutlinepoints) · [PcbPad](#pcbpad) · [PcbPadLayer](#pcbpadlayer) · [PcbPadThermal](#pcbpadthermal) · [PcbPads](#pcbpads) · [PcbPairCenter](#pcbpaircenter) · [PcbPairCenters](#pcbpaircenters) · [PcbPairSegment](#pcbpairsegment) · [PcbPairSegments](#pcbpairsegments) · [PcbPairSidePoint](#pcbpairsidepoint) · [PcbPairedPad](#pcbpairedpad) · [PcbPairedPads](#pcbpairedpads) · [PcbPanel](#pcbpanel) · [PcbPanelTabPosition](#pcbpaneltabposition) · [PcbPanelTabPositions](#pcbpaneltabpositions) · [PcbPattern](#pcbpattern) · [PcbPatternDimension](#pcbpatterndimension) · [PcbPatternDimensions](#pcbpatterndimensions) · [PcbPatternDrawing](#pcbpatterndrawing) · [PcbPatternDrawings](#pcbpatterndrawings) · [PcbPositivePoints](#pcbpositivepoints) · [PcbPositiveTraces](#pcbpositivetraces) · [PcbPourFill](#pcbpourfill) · [PcbPourRegion](#pcbpourregion) · [PcbPourRegions](#pcbpourregions) · [PcbRatline](#pcbratline) · [PcbRatlines](#pcbratlines) · [PcbRemovedDifferentialPair](#pcbremoveddifferentialpair) · [PcbRemovedDifferentialPairs](#pcbremoveddifferentialpairs) · [PcbRouteLayer](#pcbroutelayer) · [PcbRouteLayers](#pcbroutelayers) · [PcbRoutingSettings](#pcbroutingsettings) · [PcbSeparateTrace](#pcbseparatetrace) · [PcbSettings](#pcbsettings) · [PcbSheetSettings](#pcbsheetsettings) · [PcbSpokeLine](#pcbspokeline) · [PcbSpokeLines](#pcbspokelines) · [PcbTable](#pcbtable) · [PcbTableComponentRow](#pcbtablecomponentrow) · [PcbTableComponentRows](#pcbtablecomponentrows) · [PcbTableRowComponent](#pcbtablerowcomponent) · [PcbTableUpdate](#pcbtableupdate) · [PcbTableUpdateColumn](#pcbtableupdatecolumn) · [PcbTableUpdateColumns](#pcbtableupdatecolumns) · [PcbTables](#pcbtables) · [PcbTeardrop](#pcbteardrop) · [PcbTeardrops](#pcbteardrops) · [PcbTitleBlock](#pcbtitleblock) · [PcbTitleBlocks](#pcbtitleblocks) · [PcbTitleCell](#pcbtitlecell) · [PcbTitleCells](#pcbtitlecells) · [PcbTitleFields](#pcbtitlefields) · [PcbTrace](#pcbtrace) · [PcbTracePoint](#pcbtracepoint) · [PcbTracePoints](#pcbtracepoints) · [PcbTraceTeardrop](#pcbtraceteardrop) · [PcbTraceTeardrops](#pcbtraceteardrops) · [PcbTraces](#pcbtraces) · [PcbUnresolvedCheckTarget](#pcbunresolvedchecktarget) · [PcbUserField](#pcbuserfield) · [PcbUserFields](#pcbuserfields) · [PcbVectorPicture](#pcbvectorpicture) · [PcbVectorPoint](#pcbvectorpoint) · [PcbVectorPoints](#pcbvectorpoints) · [PcbVectorPolygon](#pcbvectorpolygon) · [PcbVectorPolygons](#pcbvectorpolygons) · [PcbViaStyle](#pcbviastyle) · [PcbViaStyles](#pcbviastyles) · [Point](#point) · [Points](#points) · [PossibleName](#possiblename) · [PossibleNames](#possiblenames) · [Prices](#prices) · [ProjectFolders](#projectfolders) · [ProjectLibraries](#projectlibraries) · [Quote](#quote) · [RowHeight](#rowheight) · [RowHeights](#rowheights) · [SchematicHierarchyBlock](#schematichierarchyblock) · [SchematicHierarchyBlocks](#schematichierarchyblocks) · [SchematicHierarchyPath](#schematichierarchypath) · [SchematicHierarchyPathItem](#schematichierarchypathitem) · [SchematicHierarchySheet](#schematichierarchysheet) · [SchematicHierarchySheets](#schematichierarchysheets) · [Slots](#slots) · [Subfolders](#subfolders) · [Suppliers](#suppliers) · [TableCells](#tablecells) · [TeardropParameters](#teardropparameters) · [TextLine](#textline) · [TextLines](#textlines) · [TitleField](#titlefield) · [UnresolvedKey](#unresolvedkey) · [UnresolvedKeys](#unresolvedkeys) · [UserField](#userfield) · [UserFields](#userfields)

## BlindPadLayers

| Child | Record type | Count |
| --- | --- | --- |
| Item | [PcbPadLayer](#pcbpadlayer) | 0..many |

## Board

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| RefDes_Global_SilkShow | integer | no | no | — | — | stored |
| RefDes_Global_SilkAlign | integer | no | no | — | — | stored |
| RefDes_Global_AssyShow | integer | no | no | — | — | stored |
| RefDes_Global_AssyAlign | integer | no | no | — | — | stored |
| Name_Global_SilkShow | integer | no | no | — | — | stored |
| Name_Global_SilkAlign | integer | no | no | — | — | stored |
| Name_Global_AssyShow | integer | no | no | — | — | stored |
| Name_Global_AssyAlign | integer | no | no | — | — | stored |
| Value_Global_SilkShow | integer | no | no | — | — | stored |
| Value_Global_SilkAlign | integer | no | no | — | — | stored |
| Value_Global_AssyShow | integer | no | no | — | — | stored |
| Value_Global_AssyAlign | integer | no | no | — | — | stored |
| Pattern_Global_SilkShow | integer | no | no | — | — | stored |
| Pattern_Global_SilkAlign | integer | no | no | — | — | stored |
| Pattern_Global_AssyShow | integer | no | no | — | — | stored |
| Pattern_Global_AssyAlign | integer | no | no | — | — | stored |
| Manufacturer_Global_SilkShow | integer | no | no | — | — | stored |
| Manufacturer_Global_SilkAlign | integer | no | no | — | — | stored |
| Manufacturer_Global_AssyShow | integer | no | no | — | — | stored |
| Manufacturer_Global_AssyAlign | integer | no | no | — | — | stored |
| Datasheet_Global_SilkShow | integer | no | no | — | — | stored |
| Datasheet_Global_SilkAlign | integer | no | no | — | — | stored |
| Datasheet_Global_AssyShow | integer | no | no | — | — | stored |
| Datasheet_Global_AssyAlign | integer | no | no | — | — | stored |
| RelSchem | text | no | no | — | — | stored |
| RelSchem_Variable | text | no | no | — | — | stored |
| ProjectDir | text | no | no | — | — | stored |
| CompFontName | text | no | no | — | — | stored |
| UserField1 | text | no | no | — | — | stored |
| UserField2 | text | no | no | — | — | stored |
| ProjectLibs_Name | text | no | no | — | — | stored |
| Locked | boolean | no | no | — | — | stored |
| Toplock | boolean | no | no | — | — | stored |
| Bottomlock | boolean | no | no | — | — | stored |
| PanelExclude | boolean | no | no | — | — | stored |
| RailShow | boolean | no | no | — | — | stored |
| PatternFontVector | boolean | no | no | — | — | stored |
| AssyObjSilk | boolean | no | no | — | — | stored |
| AssyObjBorders | boolean | no | no | — | — | stored |
| AssyObjMarking | boolean | no | no | — | — | stored |
| AssyObjBoard | boolean | no | no | — | — | stored |
| AssyObjPads | boolean | no | no | — | — | stored |
| CompRotate | boolean | no | no | — | — | stored |
| LockNetStructure | boolean | no | no | — | — | stored |
| SchemNetClasses | boolean | no | no | — | — | stored |
| ProjectLibs_Sorted | boolean | no | no | — | — | stored |
| CompFontMono | boolean | no | no | `False` | — | stored |
| PanelX | integer | no | no | — | — | stored |
| PanelY | integer | no | no | — | — | stored |
| ProjectLibs_Type | integer | no | no | — | — | stored |
| ProjectLibs_Content | integer | no | no | — | — | stored |
| DesignCache_Count | integer | no | no | — | — | stored |
| PanelDX | number | no | no | — | shared length | stored |
| PanelDY | number | no | no | — | shared length | stored |
| RailLeft | number | no | no | — | shared length | stored |
| RailRight | number | no | no | — | shared length | stored |
| RailTop | number | no | no | — | shared length | stored |
| RailBottom | number | no | no | — | shared length | stored |
| OriginX | number | no | no | — | shared length | stored |
| OriginY | number | no | no | — | shared length | stored |
| CompFontSize | number | no | no | — | — | stored |
| PatternFontWidth | number | no | no | — | — | stored |
| PatternFontScale | number | no | no | — | — | stored |
| Enabled | boolean | no | no | `True` | — | stored |
| Selected | boolean | no | no | `False` | — | stored |
| ShieldGroup | integer | no | no | `-1` | — | stored |
| LayerStackName | text | no | no | `''` | — | stored |
| ClassToClass | boolean | no | no | `False` | — | stored |
| DefaultClass | reference | no | yes | — | — | relationship |

| Child | Record type | Count |
| --- | --- | --- |
| AssemblyVariants | [PcbAssemblyVariants](#pcbassemblyvariants) | 0..1 |
| Layers | [PcbCopperLayers](#pcbcopperlayers) | 0..1 |
| Ratlines | [PcbRatlines](#pcbratlines) | 0..1 |
| DesignErrors | [PcbDesignErrors](#pcbdesignerrors) | 0..1 |
| ViaStyles | [PcbViaStyles](#pcbviastyles) | 0..1 |
| NetClasses | [PcbNetClasses](#pcbnetclasses) | 0..1 |
| LayerStackItems | [PcbLayerStackItems](#pcblayerstackitems) | 0..1 |
| ClassClearances | [PcbClassClearances](#pcbclassclearances) | 0..1 |
| DRC | [PcbDesignRules](#pcbdesignrules) | 0..1 |
| LastDRC | [PcbDesignRules](#pcbdesignrules) | 0..1 |
| MainLengthRule | [PcbLengthRule](#pcblengthrule) | 0..1 |
| LengthRules | [PcbLengthRules](#pcblengthrules) | 0..1 |
| Points | [PcbOutlinePoints](#pcboutlinepoints) | 0..1 |
| Groups | [PcbGroups](#pcbgroups) | 0..1 |
| NonSignals | [PcbNonSignalLayers](#pcbnonsignallayers) | 0..1 |
| Shapes | [PcbBoardDrawings](#pcbboarddrawings) | 0..1 |
| CopperPours | [PcbCopperPours](#pcbcopperpours) | 0..1 |
| Tables | [PcbTables](#pcbtables) | 0..1 |
| Dimensions | [PcbDimensions](#pcbdimensions) | 0..1 |
| Components | [PcbComponents](#pcbcomponents) | 1..1 |
| Nets | [PcbNets](#pcbnets) | 1..1 |
| DifferentialPairs | [PcbDifferentialPairs](#pcbdifferentialpairs) | 0..1 |
| RemovedDifferentialPairs | [PcbRemovedDifferentialPairs](#pcbremoveddifferentialpairs) | 0..1 |
| HierarchySheets | [SchematicHierarchySheets](#schematichierarchysheets) | 0..1 |
| Settings | [PcbSettings](#pcbsettings) | 0..1 |
| SheetSettings | [PcbSheetSettings](#pcbsheetsettings) | 0..1 |
| Panel | [PcbPanel](#pcbpanel) | 0..1 |
| ConnectivityCheck | [PcbConnectivityCheck](#pcbconnectivitycheck) | 0..1 |
| CacheLib | [CacheLibrary](#cachelibrary) | 0..1 |
| ProjectLibs_Folders | [ProjectFolders](#projectfolders) | 0..1 |
| ProjectLibs_Libs | [ProjectLibraries](#projectlibraries) | 0..1 |
| DesignCache_Links | [DesignCacheLinks](#designcachelinks) | 0..1 |
| Userfields_Global | [PcbGlobalUserFields](#pcbglobaluserfields) | 0..1 |

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
| Datasheet | text | no | no | — | — | stored |
| Name | text | yes | no | `''` | — | stored |
| RefDes | text | yes | no | `''` | — | stored |
| Verification | tuple | yes | no | `(False, False, False, False, False, False, False)` | — | stored; Seven compatibility verification states in their established order. |
| ↳ items | boolean | — | — | — | — | 7 items |

| Child | Record type | Count |
| --- | --- | --- |
| Component_CategoryTypes | [Classifications](#classifications) | 0..1 |
| Pins | [LibraryPins](#librarypins) | 0..1 |
| Shapes | [LibrarySymbolDrawings](#librarysymboldrawings) | 0..1 |
| UserFields | [ComponentUserFields](#componentuserfields) | 0..1 |
| Groups | [PcbLocalGroups](#pcblocalgroups) | 0..1 |
| ModelBody | [ModelBody](#modelbody) | 0..1 |
| Suppliers | [Suppliers](#suppliers) | 0..1 |

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

## DesignCacheLink

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| SlotIndex | integer | yes | no | `-1` | — | stored; Managed library-slot index in the active prefix; a literal capacity value beyond it. |

## DesignCacheLinks

An ordered collection of DesignCacheLink records.

| Child | Record type | Count |
| --- | --- | --- |
| Link | [DesignCacheLink](#designcachelink) | 0..many |

## HiddenPadLayers

| Child | Record type | Count |
| --- | --- | --- |
| Item | [PcbPadLayer](#pcbpadlayer) | 0..many |

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

## LibraryDefinition

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Index | integer | no | no | — | — | calculated; Current zero-based variant position within its library slot. |

| Child | Record type | Count |
| --- | --- | --- |
| Part | [CachedPart](#cachedpart) | 0..1 |
| Pattern | [Pattern](#pattern) | 0..1 |

## LibraryDimension

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
| Group | reference | no | yes | — | — | relationship |
| FontMono | boolean | no | no | `False` | — | stored |
| Index | integer | yes | no | `0` | — | calculated |
| GroupId | integer | no | no | — | — | calculated |
| UnresolvedGroupId | integer | no | no | — | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| UnresolvedKeys | [UnresolvedKeys](#unresolvedkeys) | 0..1 |

## LibraryDimensions

| Child | Record type | Count |
| --- | --- | --- |
| Dimension | [LibraryDimension](#librarydimension) | 0..many |

## LibraryHole

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Enabled | boolean | yes | no | `False` | — | stored |
| Locked | boolean | yes | no | `False` | — | stored |
| X | number | yes | no | `0` | shared length | stored |
| Y | number | yes | no | `0` | shared length | stored |
| Diam | number | yes | no | `0` | shared length | stored; Outer diameter. |
| HoleDiam | number | yes | no | `0` | shared length | stored; Drill diameter. |
| Group | reference | no | yes | — | — | relationship |
| GroupId | integer | no | no | — | — | calculated |
| UnresolvedGroupId | integer | no | no | — | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| UnresolvedKeys | [UnresolvedKeys](#unresolvedkeys) | 0..1 |

## LibraryHoles

| Child | Record type | Count |
| --- | --- | --- |
| Hole | [LibraryHole](#libraryhole) | 0..many |

## LibraryInternalConnections

| Child | Record type | Count |
| --- | --- | --- |
| IntCon | [PcbInternalConnectionDefinition](#pcbinternalconnectiondefinition) | 0..many |

## LibraryPad

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
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
| Group | reference | no | yes | — | — | relationship |
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
| GroupId | integer | no | no | — | — | calculated |
| UnresolvedGroupId | integer | no | no | — | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| PadMask_TopSegments | [PasteSegments](#pastesegments) | 0..1 |
| PadMask_BotSegments | [PasteSegments](#pastesegments) | 0..1 |
| PadPoints_New | [Points](#points) | 0..1 |
| PadTerminal | [PadTerminal](#padterminal) | 0..many |
| UnresolvedKeys | [UnresolvedKeys](#unresolvedkeys) | 0..1 |

## LibraryPads

| Child | Record type | Count |
| --- | --- | --- |
| Pad | [LibraryPad](#librarypad) | 0..many |

## LibraryPath

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Path | text | yes | no | `''` | — | stored |
| VariablePath | text | no | no | `''` | — | stored |

## LibraryPatternDrawing

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
| Group | reference | no | yes | — | — | relationship |
| PadId | integer | no | no | — | — | calculated |
| Index | integer | yes | no | `0` | — | calculated |
| Pad | reference | no | yes | — | — | relationship |
| ShieldGroup | integer | no | no | `-1` | — | stored |
| GroupId | integer | no | no | — | — | calculated |
| UnresolvedGroupId | integer | no | no | — | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| Points_New | [Points](#points) | 0..1 |
| TextLine | [TextLines](#textlines) | 0..1 |
| UnresolvedKeys | [UnresolvedKeys](#unresolvedkeys) | 0..1 |

## LibraryPatternDrawings

| Child | Record type | Count |
| --- | --- | --- |
| Shape | [LibraryPatternDrawing](#librarypatterndrawing) | 0..many |

## LibraryPin

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
| Group | reference | no | yes | — | — | relationship |
| PinNameRotate | number | yes | no | — | — | stored |
| PinNumRotate | number | yes | no | — | — | stored |
| NameFontMono | boolean | no | no | `False` | — | stored |
| SignalDelay | number | no | no | — | — | stored |
| Index | integer | yes | no | `0` | — | calculated |
| X | number | yes | no | `0` | shared length | stored |
| Y | number | yes | no | `0` | shared length | stored |
| GroupId | integer | no | no | — | — | calculated |
| UnresolvedGroupId | integer | no | no | — | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| UnresolvedKeys | [UnresolvedKeys](#unresolvedkeys) | 0..1 |

## LibraryPins

| Child | Record type | Count |
| --- | --- | --- |
| Pin | [LibraryPin](#librarypin) | 0..many |

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

## LibrarySymbolDrawing

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
| Group | reference | no | yes | — | — | relationship |
| ShowPart | boolean | yes | no | — | — | stored |
| MarkingGenerated | boolean | yes | no | — | — | stored |
| Locked | boolean | yes | no | — | — | stored |
| VectorFont | boolean | yes | no | — | — | stored |
| FontWidth | number | yes | no | — | — | stored |
| FontScale | number | yes | no | — | — | stored |
| FontMono | boolean | no | no | `False` | — | stored |
| Index | integer | yes | no | `0` | — | calculated |
| GroupId | integer | no | no | — | — | calculated |
| UnresolvedGroupId | integer | no | no | — | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| Points_New | [Points](#points) | 0..1 |
| TextLine | [TextLines](#textlines) | 0..1 |
| UnresolvedKeys | [UnresolvedKeys](#unresolvedkeys) | 0..1 |

## LibrarySymbolDrawings

| Child | Record type | Count |
| --- | --- | --- |
| Shape | [LibrarySymbolDrawing](#librarysymboldrawing) | 0..many |

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

## PadThermals

| Child | Record type | Count |
| --- | --- | --- |
| CustomSpoke | [PcbPadThermal](#pcbpadthermal) | 0..many |

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
| Value | text | no | no | — | — | stored; Default value supplied by an unplaced footprint template. |

| Child | Record type | Count |
| --- | --- | --- |
| Pattern_CategoryTypes | [Classifications](#classifications) | 0..1 |
| PossibleNames | [PossibleNames](#possiblenames) | 0..1 |
| PadMask_TopSegments | [PasteSegments](#pastesegments) | 0..1 |
| PadMask_BotSegments | [PasteSegments](#pastesegments) | 0..1 |
| Pads | [LibraryPads](#librarypads) | 0..1 |
| Shapes | [LibraryPatternDrawings](#librarypatterndrawings) | 0..1 |
| Holes | [LibraryHoles](#libraryholes) | 0..1 |
| Dimensions | [LibraryDimensions](#librarydimensions) | 0..1 |
| UserFields | [UserFields](#userfields) | 0..1 |
| Model3D | [Model3D](#model3d) | 0..1 |
| Pattern_Groups | [PcbLocalGroups](#pcblocalgroups) | 0..1 |
| InternalConnections | [LibraryInternalConnections](#libraryinternalconnections) | 0..1 |
| PadPoints | [Points](#points) | 0..1 |
| PadTerminal | [PadTerminal](#padterminal) | 0..many |

## Patterns

| Child | Record type | Count |
| --- | --- | --- |
| Pattern | [Pattern](#pattern) | 0..many |

## PcbAllowedVia

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Via | reference | no | yes | — | — | relationship |
| Id | integer | no | no | — | — | calculated |

## PcbAllowedVias

| Child | Record type | Count |
| --- | --- | --- |
| ViaStyle | [PcbAllowedVia](#pcballowedvia) | 0..many |

## PcbAssemblyExclusion

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Variant | reference | no | yes | — | — | relationship |
| Index | integer | no | no | — | — | calculated |
| UnresolvedIndex | integer | no | no | — | — | stored |

## PcbAssemblyExclusions

| Child | Record type | Count |
| --- | --- | --- |
| Item | [PcbAssemblyExclusion](#pcbassemblyexclusion) | 0..many |

## PcbAssemblyVariant

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Name | text | yes | no | `''` | — | stored |
| Id | integer | no | no | — | — | calculated |

## PcbAssemblyVariants

| Child | Record type | Count |
| --- | --- | --- |
| AssemblyVariant | [PcbAssemblyVariant](#pcbassemblyvariant) | 0..many |

## PcbBoardDrawing

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Id | integer | no | no | — | — | calculated |
| Group | reference | no | yes | — | — | relationship |
| GroupId | integer | no | no | — | — | calculated |
| Net | reference | no | yes | — | — | relationship |
| NetId | integer | no | no | — | — | calculated |
| NetNumber | integer | no | no | — | — | calculated |
| LayerTarget | reference | no | yes | — | — | relationship |
| LayId | integer | no | no | — | — | calculated |
| Enabled | boolean | no | no | `False` | — | stored |
| Selected | boolean | no | no | `False` | — | stored |
| AllLayers | boolean | no | no | `False` | — | stored |
| Locked | boolean | no | no | `False` | — | stored |
| VectorFont | boolean | no | no | `False` | — | stored |
| PanelExclude | boolean | no | no | `False` | — | stored |
| Inverted | boolean | no | no | `False` | — | stored |
| PictureProportions | boolean | no | no | `False` | — | stored |
| PictureRaster | boolean | no | no | `False` | — | stored |
| PictureFlipped | boolean | no | no | `False` | — | stored |
| FontMono | boolean | no | no | `False` | — | stored |
| Layer | integer | no | no | `0` | — | stored |
| Type | integer | no | no | `0` | — | stored |
| Color | integer | no | no | `0` | — | stored |
| BrushColor | integer | no | no | `0` | — | stored |
| FontColor | integer | no | no | `0` | — | stored |
| TextHorz | integer | no | no | `0` | — | stored |
| TextVert | integer | no | no | `0` | — | stored |
| TextAlign | integer | no | no | `0` | — | stored |
| ShieldGroup | integer | no | no | `-1` | — | stored |
| PenWidth | number | no | no | `0` | — | stored |
| FontSize | number | no | no | `0` | — | stored |
| FontWidth | number | no | no | `0` | — | stored |
| FontScale | number | no | no | `0` | — | stored |
| LineSpacing | number | no | no | `0` | — | stored |
| TextAngle | number | no | no | `0` | — | stored |
| PictureWidth | number | no | no | `0` | — | stored |
| PictureHeight | number | no | no | `0` | — | stored |
| PictureTransparent | number | no | no | `0` | — | stored |
| FontName | text | no | no | `''` | — | stored |
| Picture_File | text | no | no | `''` | — | stored |
| Picture_File_Variable | text | no | no | `''` | — | stored |
| BitmapIndex | integer | no | no | `-1` | — | stored; Unresolved external companion-table reference; -1 when file-backed or unassigned. |

| Child | Record type | Count |
| --- | --- | --- |
| Points | [Points](#points) | 0..1 |
| TextLine | [TextLines](#textlines) | 0..1 |
| PictureVector | [PcbVectorPicture](#pcbvectorpicture) | 0..1 |

## PcbBoardDrawings

| Child | Record type | Count |
| --- | --- | --- |
| Shape | [PcbBoardDrawing](#pcbboarddrawing) | 0..many |

## PcbBorderZones

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Visible | boolean | no | no | — | — | stored |
| Border | boolean | no | no | — | — | stored |
| HorzZones | integer | no | no | — | — | stored |
| VertZones | integer | no | no | — | — | stored |
| Standard | integer | no | no | — | — | stored |
| FontName | text | no | no | — | — | stored |
| FontSize | number | no | no | — | — | stored |
| HorzBorderSize | number | no | no | — | shared length | stored |
| VertBorderSize | number | no | no | — | shared length | stored |
| FontLineWidth | number | no | no | — | shared length | stored |

## PcbClassClearance

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Class1 | reference | no | yes | — | — | relationship |
| Class2 | reference | no | yes | — | — | relationship |
| NetClass1 | integer | no | no | — | — | calculated |
| NetClass2 | integer | no | no | — | — | calculated |
| AllLayers | boolean | no | no | `True` | — | stored |
| Clearance | number | no | yes | `None` | shared length | stored |

| Child | Record type | Count |
| --- | --- | --- |
| LayerClearances | [PcbLayerClearances](#pcblayerclearances) | 0..1 |

## PcbClassClearanceDetails

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| TraceToTrace | number | no | no | `-1` | shared length | stored |
| TraceToVia | number | no | no | `-1` | shared length | stored |
| TraceToPad | number | no | no | `-1` | shared length | stored |
| TraceToSmd | number | no | no | `-1` | shared length | stored |
| TraceToCopper | number | no | no | `-1` | shared length | stored |
| ViaToVia | number | no | no | `-1` | shared length | stored |
| ViaToPad | number | no | no | `-1` | shared length | stored |
| ViaToSmd | number | no | no | `-1` | shared length | stored |
| ViaToCopper | number | no | no | `-1` | shared length | stored |
| PadToPad | number | no | no | `-1` | shared length | stored |
| PadToSmd | number | no | no | `-1` | shared length | stored |
| PadToCopper | number | no | no | `-1` | shared length | stored |
| SmdToSmd | number | no | no | `-1` | shared length | stored |
| SmdToCopper | number | no | no | `-1` | shared length | stored |

## PcbClassClearances

| Child | Record type | Count |
| --- | --- | --- |
| Cell | [PcbClassClearance](#pcbclassclearance) | 0..many |

## PcbClassLayerProperties

| Child | Record type | Count |
| --- | --- | --- |
| LayProperty | [PcbClassLayerProperty](#pcbclasslayerproperty) | 0..many |

## PcbClassLayerProperty

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Layer | reference | no | yes | — | — | relationship |
| Lay | integer | no | no | — | — | calculated |
| LayerName | text | no | no | — | — | calculated |
| Width | number | no | no | `-1` | shared length | stored |
| MinWidth | number | no | no | `-1` | shared length | stored |
| MaxWidth | number | no | no | `-1` | shared length | stored |
| Clearance | number | no | no | `-1` | shared length | stored |
| DifClearance | number | no | no | `-1` | shared length | stored |
| Neck_Width | number | no | no | `-1` | shared length | stored |
| Neck_DifClearance | number | no | no | `-1` | shared length | stored |
| Neck_MaxLength | number | no | no | `-1` | shared length | stored |

| Child | Record type | Count |
| --- | --- | --- |
| ClearanceDetails | [PcbClassClearanceDetails](#pcbclassclearancedetails) | 0..1 |

## PcbClassLengthResults

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| AnyError | boolean | no | no | — | — | calculated; Aggregate of the stored connection error results; does not calculate route length. |

| Child | Record type | Count |
| --- | --- | --- |
| Rules | [PcbLengthConnections](#pcblengthconnections) | 0..1 |

## PcbComponent

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| RefDes_SilkShow | integer | no | no | `0` | — | stored |
| RefDes_SilkAlign | integer | no | no | `0` | — | stored |
| RefDes_SilkHorz | integer | no | no | `0` | — | stored |
| RefDes_SilkVert | integer | no | no | `0` | — | stored |
| RefDes_SilkX | number | no | no | `0` | shared length | stored |
| RefDes_SilkY | number | no | no | `0` | shared length | stored |
| RefDes_SilkAngle | number | no | no | `0` | radians | stored |
| RefDes_AssyShow | integer | no | no | `0` | — | stored |
| RefDes_AssyAlign | integer | no | no | `0` | — | stored |
| RefDes_AssyHorz | integer | no | no | `0` | — | stored |
| RefDes_AssyVert | integer | no | no | `0` | — | stored |
| RefDes_AssyX | number | no | no | `0` | shared length | stored |
| RefDes_AssyY | number | no | no | `0` | shared length | stored |
| RefDes_AssyAngle | number | no | no | `0` | radians | stored |
| Name_SilkShow | integer | no | no | `0` | — | stored |
| Name_SilkAlign | integer | no | no | `0` | — | stored |
| Name_SilkHorz | integer | no | no | `0` | — | stored |
| Name_SilkVert | integer | no | no | `0` | — | stored |
| Name_SilkX | number | no | no | `0` | shared length | stored |
| Name_SilkY | number | no | no | `0` | shared length | stored |
| Name_SilkAngle | number | no | no | `0` | radians | stored |
| Name_AssyShow | integer | no | no | `0` | — | stored |
| Name_AssyAlign | integer | no | no | `0` | — | stored |
| Name_AssyHorz | integer | no | no | `0` | — | stored |
| Name_AssyVert | integer | no | no | `0` | — | stored |
| Name_AssyX | number | no | no | `0` | shared length | stored |
| Name_AssyY | number | no | no | `0` | shared length | stored |
| Name_AssyAngle | number | no | no | `0` | radians | stored |
| Value_SilkShow | integer | no | no | `0` | — | stored |
| Value_SilkAlign | integer | no | no | `0` | — | stored |
| Value_SilkHorz | integer | no | no | `0` | — | stored |
| Value_SilkVert | integer | no | no | `0` | — | stored |
| Value_SilkX | number | no | no | `0` | shared length | stored |
| Value_SilkY | number | no | no | `0` | shared length | stored |
| Value_SilkAngle | number | no | no | `0` | radians | stored |
| Value_AssyShow | integer | no | no | `0` | — | stored |
| Value_AssyAlign | integer | no | no | `0` | — | stored |
| Value_AssyHorz | integer | no | no | `0` | — | stored |
| Value_AssyVert | integer | no | no | `0` | — | stored |
| Value_AssyX | number | no | no | `0` | shared length | stored |
| Value_AssyY | number | no | no | `0` | shared length | stored |
| Value_AssyAngle | number | no | no | `0` | radians | stored |
| Pattern_SilkShow | integer | no | no | `0` | — | stored |
| Pattern_SilkAlign | integer | no | no | `0` | — | stored |
| Pattern_SilkHorz | integer | no | no | `0` | — | stored |
| Pattern_SilkVert | integer | no | no | `0` | — | stored |
| Pattern_SilkX | number | no | no | `0` | shared length | stored |
| Pattern_SilkY | number | no | no | `0` | shared length | stored |
| Pattern_SilkAngle | number | no | no | `0` | radians | stored |
| Pattern_AssyShow | integer | no | no | `0` | — | stored |
| Pattern_AssyAlign | integer | no | no | `0` | — | stored |
| Pattern_AssyHorz | integer | no | no | `0` | — | stored |
| Pattern_AssyVert | integer | no | no | `0` | — | stored |
| Pattern_AssyX | number | no | no | `0` | shared length | stored |
| Pattern_AssyY | number | no | no | `0` | shared length | stored |
| Pattern_AssyAngle | number | no | no | `0` | radians | stored |
| Manufacturer_SilkShow | integer | no | no | `0` | — | stored |
| Manufacturer_SilkAlign | integer | no | no | `0` | — | stored |
| Manufacturer_SilkHorz | integer | no | no | `0` | — | stored |
| Manufacturer_SilkVert | integer | no | no | `0` | — | stored |
| Manufacturer_SilkX | number | no | no | `0` | shared length | stored |
| Manufacturer_SilkY | number | no | no | `0` | shared length | stored |
| Manufacturer_SilkAngle | number | no | no | `0` | radians | stored |
| Manufacturer_AssyShow | integer | no | no | `0` | — | stored |
| Manufacturer_AssyAlign | integer | no | no | `0` | — | stored |
| Manufacturer_AssyHorz | integer | no | no | `0` | — | stored |
| Manufacturer_AssyVert | integer | no | no | `0` | — | stored |
| Manufacturer_AssyX | number | no | no | `0` | shared length | stored |
| Manufacturer_AssyY | number | no | no | `0` | shared length | stored |
| Manufacturer_AssyAngle | number | no | no | `0` | radians | stored |
| Datasheet_SilkShow | integer | no | no | `0` | — | stored |
| Datasheet_SilkAlign | integer | no | no | `0` | — | stored |
| Datasheet_SilkHorz | integer | no | no | `0` | — | stored |
| Datasheet_SilkVert | integer | no | no | `0` | — | stored |
| Datasheet_SilkX | number | no | no | `0` | shared length | stored |
| Datasheet_SilkY | number | no | no | `0` | shared length | stored |
| Datasheet_SilkAngle | number | no | no | `0` | radians | stored |
| Datasheet_AssyShow | integer | no | no | `0` | — | stored |
| Datasheet_AssyAlign | integer | no | no | `0` | — | stored |
| Datasheet_AssyHorz | integer | no | no | `0` | — | stored |
| Datasheet_AssyVert | integer | no | no | `0` | — | stored |
| Datasheet_AssyX | number | no | no | `0` | shared length | stored |
| Datasheet_AssyY | number | no | no | `0` | shared length | stored |
| Datasheet_AssyAngle | number | no | no | `0` | radians | stored |
| Name | text | no | no | `''` | — | stored |
| RefDes | text | no | no | `''` | — | stored |
| Value | text | no | no | `''` | — | stored |
| BaseName | text | no | no | `''` | — | stored |
| LibPath | text | no | no | `''` | — | stored |
| LibPath_Variable | text | no | no | `''` | — | stored |
| Manufacturer | text | no | no | `''` | — | stored |
| Datasheet | text | no | no | `''` | — | stored |
| Selected | boolean | no | no | `False` | — | stored |
| Locked | boolean | no | no | `False` | — | stored |
| PanelExclude | boolean | no | no | `False` | — | stored |
| BottomSide | boolean | no | no | `False` | — | stored |
| Flipped | boolean | no | no | `False` | — | stored |
| HorizontalFlip | boolean | no | no | `False` | — | stored |
| CustomMarkingFont | boolean | no | no | `False` | — | stored |
| MarkingFontAll | boolean | no | no | `False` | — | stored |
| HiddenId | integer | no | no | `0` | — | stored |
| GsType | integer | no | no | `0` | — | stored |
| ShowFiducial | integer | no | no | `0` | — | stored |
| ShieldGroup | integer | no | no | `-1` | — | stored |
| Group | reference | no | yes | — | — | relationship |
| GroupId | integer | no | no | — | — | calculated |
| Layer | reference | no | yes | — | — | relationship |
| ConnectedLayer | integer | no | no | — | — | calculated |
| Via | reference | no | yes | — | — | relationship |
| ViaStyle | integer | no | no | — | — | calculated |
| Enabled | boolean | yes | no | `True` | — | stored |
| X | number | yes | no | `0` | shared length | stored |
| Y | number | yes | no | `0` | shared length | stored |
| Angle | number | yes | no | `0` | radians | stored |
| PlacementClearance | number | no | no | `-1` | shared length | stored |
| MarkingFontSize | number | no | no | `5` | — | stored |
| Component_CategoryName | text | no | no | `''` | — | stored |
| Component_CategoryIndex | integer | no | no | `-1` | — | stored |
| Number | integer | no | no | — | — | calculated |

| Child | Record type | Count |
| --- | --- | --- |
| Pattern | [PcbPattern](#pcbpattern) | 1..1 |
| Suppliers | [Suppliers](#suppliers) | 0..1 |
| AssemblyExclude | [PcbAssemblyExclusions](#pcbassemblyexclusions) | 0..1 |
| UserFields | [PcbUserFields](#pcbuserfields) | 0..1 |
| IntConRecords | [PcbInternalConnectionDefinitions](#pcbinternalconnectiondefinitions) | 0..1 |
| HierarchyPath | [SchematicHierarchyPath](#schematichierarchypath) | 0..1 |
| InternalConnections | [PcbInternalConnectionPolicies](#pcbinternalconnectionpolicies) | 0..1 |
| Component_CategoryTypes | [Classifications](#classifications) | 0..1 |

## PcbComponents

| Child | Record type | Count |
| --- | --- | --- |
| Component | [PcbComponent](#pcbcomponent) | 0..many |

## PcbConnectivityCheck

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Traces | boolean | no | no | — | — | stored |
| Shapes | boolean | no | no | — | — | stored |
| CopperPours | boolean | no | no | — | — | stored |

## PcbCopperLayer

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Name | text | yes | no | `''` | — | stored |
| Number | integer | no | no | — | — | calculated |
| Enabled | boolean | no | no | `True` | — | stored |
| Color | integer | no | no | `0` | — | stored |
| Type | integer | no | no | `0` | — | stored |
| HoleType | integer | no | no | `0` | — | stored |
| HoleRing | number | no | no | `0` | shared length | stored |
| Locked | boolean | no | no | `False` | — | stored |
| Net | reference | no | yes | — | — | relationship |
| NetNumber | integer | no | no | — | — | calculated |

## PcbCopperLayers

| Child | Record type | Count |
| --- | --- | --- |
| Layer | [PcbCopperLayer](#pcbcopperlayer) | 0..many |

## PcbCopperPour

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Id | integer | no | no | — | — | calculated |
| Group | reference | no | yes | — | — | relationship |
| GroupId | integer | no | no | — | — | calculated |
| Net | reference | no | yes | — | — | relationship |
| NetId | integer | no | no | — | — | calculated |
| NetNumber | integer | no | no | — | — | calculated |
| Layer | reference | no | yes | — | — | relationship |
| Lay | integer | no | no | — | — | calculated |
| Enabled | boolean | no | no | `False` | — | stored |
| Selected | boolean | no | no | `False` | — | stored |
| Poured | boolean | no | no | `False` | — | stored |
| UseNetClearance | boolean | no | no | `False` | — | stored |
| Locked | boolean | no | no | `False` | — | stored |
| SnapToBoard | boolean | no | no | `False` | — | stored |
| IslandRegion | boolean | no | no | `False` | — | stored |
| IslandInternal | boolean | no | no | `False` | — | stored |
| IslandConnection | boolean | no | no | `False` | — | stored |
| ViaDirect | boolean | no | no | `False` | — | stored |
| SMD_Separate | boolean | no | no | `False` | — | stored |
| PanelExclude | boolean | no | no | `False` | — | stored |
| Type | integer | no | no | `0` | — | stored |
| Spoke | integer | no | no | `0` | — | stored |
| SMD_Spoke | integer | no | no | `0` | — | stored |
| Priority | integer | no | no | `0` | — | stored |
| RatlineMode | integer | no | no | `0` | — | stored |
| ShieldGroup | integer | no | no | `-1` | — | stored |
| TraceShieldGroup | integer | no | no | `-1` | — | stored |
| LineWidth | number | no | no | `0` | shared length | stored |
| Clearance | number | no | no | `0` | shared length | stored |
| LineSpacing | number | no | no | `0` | shared length | stored |
| SpokeWidth | number | no | no | `0` | shared length | stored |
| BoardClearance | number | no | no | `0` | shared length | stored |
| SMD_SpokeWidth | number | no | no | `0` | shared length | stored |
| MinimumArea | number | no | no | `0` | shared length squared | stored |

| Child | Record type | Count |
| --- | --- | --- |
| Points | [Points](#points) | 0..1 |
| Fill | [PcbPourFill](#pcbpourfill) | 0..1 |

## PcbCopperPours

| Child | Record type | Count |
| --- | --- | --- |
| CopperPour | [PcbCopperPour](#pcbcopperpour) | 0..many |

## PcbDesignError

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Id | integer | no | no | — | — | calculated |
| Enabled | boolean | no | no | `True` | — | stored |
| X | number | no | no | `0` | shared length | stored |
| Y | number | no | no | `0` | shared length | stored |
| Value | number | no | no | `0` | shared length | stored |
| Rule | number | no | no | `0` | shared length | stored |
| Type | integer | no | no | `0` | — | stored |
| RuleType | integer | no | no | `-1` | — | stored |
| ObjectType1 | integer | no | no | `-1` | — | stored |
| ObjectType2 | integer | no | no | `-1` | — | stored |
| Target1 | reference | no | yes | — | — | relationship |
| Object1 | integer | no | no | — | — | calculated |
| SubObject1 | integer | no | no | — | — | calculated |
| Point1 | integer | no | no | — | — | calculated |
| ExtObject1 | integer | no | no | — | — | calculated |
| Target2 | reference | no | yes | — | — | relationship |
| Object2 | integer | no | no | — | — | calculated |
| SubObject2 | integer | no | no | — | — | calculated |
| Point2 | integer | no | no | — | — | calculated |
| ExtObject2 | integer | no | no | — | — | calculated |
| NetClass1 | reference | no | yes | — | — | relationship |
| ObjectNetClass1 | integer | no | no | — | — | calculated |
| UnresolvedObjectNetClass1 | integer | no | no | — | — | stored |
| NetClass2 | reference | no | yes | — | — | relationship |
| ObjectNetClass2 | integer | no | no | — | — | calculated |
| UnresolvedObjectNetClass2 | integer | no | no | — | — | stored |
| RuleLayer | reference | no | yes | — | — | relationship |
| RuleLay | integer | no | no | — | — | calculated |
| UnresolvedRuleLay | integer | no | no | — | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| Layers | [PcbErrorLayers](#pcberrorlayers) | 0..1 |
| UnresolvedTarget1 | [PcbUnresolvedCheckTarget](#pcbunresolvedchecktarget) | 0..1 |
| UnresolvedTarget2 | [PcbUnresolvedCheckTarget](#pcbunresolvedchecktarget) | 0..1 |

## PcbDesignErrors

| Child | Record type | Count |
| --- | --- | --- |
| DesignError | [PcbDesignError](#pcbdesignerror) | 0..many |

## PcbDesignRules

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Name | text | no | no | `''` | — | stored |
| CheckClearance | boolean | no | no | `False` | — | stored |
| CheckSize | boolean | no | no | `False` | — | stored |
| CheckJumpers | boolean | no | no | `False` | — | stored |
| CheckCopperPours | boolean | no | no | `False` | — | stored |
| CheckClassToClass | boolean | no | no | `False` | — | stored |
| CheckSilk | boolean | no | no | `False` | — | stored |
| CheckLength | boolean | no | no | `False` | — | stored |
| AllLayers | boolean | no | no | `False` | — | stored |
| ShowList | boolean | no | no | `False` | — | stored |
| CheckKeepouts | boolean | no | no | `False` | — | stored |
| CheckSameNet | boolean | no | no | `False` | — | stored |
| CheckSameComponentPads | boolean | no | no | `False` | — | stored |
| CheckCourtyard | boolean | no | no | `False` | — | stored |
| DRCDone | boolean | no | no | `False` | — | stored |
| RealTimeMode | integer | no | no | `0` | — | stored |
| SilkClearance | number | no | no | `0` | shared length | stored |

| Child | Record type | Count |
| --- | --- | --- |
| LayClearances | [PcbDrcLayerClearances](#pcbdrclayerclearances) | 0..1 |
| LaySizes | [PcbDrcLayerSizes](#pcbdrclayersizes) | 0..1 |

## PcbDifferentialPair

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Class | reference | no | yes | — | — | relationship |
| NetClass | integer | no | no | — | — | calculated |
| Id | integer | no | no | — | — | calculated |
| Name | text | no | no | `''` | — | stored |
| Enabled | boolean | no | no | `True` | — | stored |
| CustomColor | boolean | no | no | `False` | — | stored |
| TraceColor | integer | no | no | `0` | — | stored |
| AutoPadPoints | boolean | no | no | `True` | — | stored |
| RouteMode | integer | no | no | `0` | — | stored |
| PosNet | reference | no | yes | — | — | relationship |
| NegNet | reference | no | yes | — | — | relationship |
| PosNetIndex | integer | no | no | — | — | calculated |
| NegNetIndex | integer | no | no | — | — | calculated |

| Child | Record type | Count |
| --- | --- | --- |
| PadPoints | [PcbPairedPads](#pcbpairedpads) | 0..1 |
| Segments | [PcbPairSegments](#pcbpairsegments) | 0..1 |
| PosSeparateTraces | [PcbPositiveTraces](#pcbpositivetraces) | 0..1 |
| NegSeparateTraces | [PcbNegativeTraces](#pcbnegativetraces) | 0..1 |

## PcbDifferentialPairs

| Child | Record type | Count |
| --- | --- | --- |
| DifferentialPair | [PcbDifferentialPair](#pcbdifferentialpair) | 0..many |

## PcbDimension

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
| Group | reference | no | yes | — | — | relationship |
| FontMono | boolean | no | no | `False` | — | stored |
| Index | integer | yes | no | `0` | — | calculated |
| GroupId | integer | no | no | — | — | calculated |
| Selected | boolean | no | no | `False` | — | stored |
| PanelExclude | boolean | no | no | `False` | — | stored |
| NonSignalLayer | reference | no | yes | — | — | relationship |
| NonSignal | integer | no | no | — | — | calculated |
| UnresolvedNonSignal | integer | no | no | — | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| UnresolvedKeys | [UnresolvedKeys](#unresolvedkeys) | 0..1 |

## PcbDimensions

| Child | Record type | Count |
| --- | --- | --- |
| Dimension | [PcbDimension](#pcbdimension) | 0..many |

## PcbDocument

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Units | text | yes | no | `'mm'` | — | stored; Display units; stored coordinates remain in shared length units. |
| Scale | number | no | no | `100` | % | stored |
| Xpos | number | no | no | `0` | shared length | stored |
| Ypos | number | no | no | `0` | shared length | stored |

| Child | Record type | Count |
| --- | --- | --- |
| Board | [Board](#board) | 1..1 |

## PcbDrcClearanceDetails

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| TraceToTrace | number | no | no | `-1` | shared length | stored |
| TraceToVia | number | no | no | `-1` | shared length | stored |
| TraceToPad | number | no | no | `-1` | shared length | stored |
| TraceToSmd | number | no | no | `-1` | shared length | stored |
| TraceToCopper | number | no | no | `-1` | shared length | stored |
| TraceToDrill | number | no | no | `-1` | shared length | stored |
| TraceToBoard | number | no | no | `-1` | shared length | stored |
| ViaToVia | number | no | no | `-1` | shared length | stored |
| ViaToPad | number | no | no | `-1` | shared length | stored |
| ViaToSmd | number | no | no | `-1` | shared length | stored |
| ViaToCopper | number | no | no | `-1` | shared length | stored |
| ViaToDrill | number | no | no | `-1` | shared length | stored |
| ViaToBoard | number | no | no | `-1` | shared length | stored |
| PadToPad | number | no | no | `-1` | shared length | stored |
| PadToSmd | number | no | no | `-1` | shared length | stored |
| PadToCopper | number | no | no | `-1` | shared length | stored |
| PadToDrill | number | no | no | `-1` | shared length | stored |
| PadToBoard | number | no | no | `-1` | shared length | stored |
| SmdToSmd | number | no | no | `-1` | shared length | stored |
| SmdToCopper | number | no | no | `-1` | shared length | stored |
| SmdToDrill | number | no | no | `-1` | shared length | stored |
| SmdToBoard | number | no | no | `-1` | shared length | stored |
| CopperToCopper | number | no | no | `-1` | shared length | stored |
| CopperToDrill | number | no | no | `-1` | shared length | stored |
| CopperToBoard | number | no | no | `-1` | shared length | stored |
| DrillToDrill | number | no | no | `-1` | shared length | stored |
| DrillToBoard | number | no | no | `-1` | shared length | stored |

## PcbDrcLayerClearance

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Layer | reference | no | yes | — | — | relationship |
| Lay | integer | no | no | — | — | calculated |
| SameTraceToTrace | number | no | no | `-1` | shared length | stored |
| SameSmdToVia | number | no | no | `-1` | shared length | stored |
| SameSmdToPad | number | no | no | `-1` | shared length | stored |
| SameSmdToSmd | number | no | no | `-1` | shared length | stored |

| Child | Record type | Count |
| --- | --- | --- |
| ClearanceDetails | [PcbDrcClearanceDetails](#pcbdrcclearancedetails) | 0..1 |

## PcbDrcLayerClearances

| Child | Record type | Count |
| --- | --- | --- |
| LayClearance | [PcbDrcLayerClearance](#pcbdrclayerclearance) | 0..many |

## PcbDrcLayerSize

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Layer | reference | no | yes | — | — | relationship |
| Lay | integer | no | no | — | — | calculated |
| MinTrace | number | no | no | `-1` | shared length | stored |
| MinDrill | number | no | no | `-1` | shared length | stored |
| MinRing | number | no | no | `-1` | shared length | stored |
| MaxRing | number | no | no | `-1` | shared length | stored |
| MaxPlatedHole | number | no | no | `-1` | shared length | stored |
| MaxNonPlatedHole | number | no | no | `-1` | shared length | stored |

## PcbDrcLayerSizes

| Child | Record type | Count |
| --- | --- | --- |
| LaySize | [PcbDrcLayerSize](#pcbdrclayersize) | 0..many |

## PcbErrorLayer

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Layer | reference | no | yes | — | — | relationship |
| Index | integer | no | no | — | — | calculated |
| UnresolvedIndex | integer | no | no | — | — | stored |

## PcbErrorLayers

| Child | Record type | Count |
| --- | --- | --- |
| Layer | [PcbErrorLayer](#pcberrorlayer) | 0..many |

## PcbFillLine

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| X1 | number | no | no | `0` | shared length | stored |
| Y1 | number | no | no | `0` | shared length | stored |
| X2 | number | no | no | `0` | shared length | stored |
| Y2 | number | no | no | `0` | shared length | stored |
| Region | reference | no | yes | — | — | relationship |
| RegionId | integer | no | no | — | — | calculated; Current group label, or -1 when unassigned; edit Region instead. |

## PcbFillLines

| Child | Record type | Count |
| --- | --- | --- |
| Line | [PcbFillLine](#pcbfillline) | 0..many |

## PcbFillPolygon

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Region | reference | no | yes | — | — | relationship |
| RegionId | integer | no | no | — | — | calculated; Current group label, or -1 when unassigned; edit Region instead. |

| Child | Record type | Count |
| --- | --- | --- |
| Points | [Points](#points) | 0..1 |

## PcbFillPolygons

| Child | Record type | Count |
| --- | --- | --- |
| Poly | [PcbFillPolygon](#pcbfillpolygon) | 0..many |

## PcbGlobalUserField

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Name | text | yes | no | `''` | — | stored |
| Value | text | no | no | — | — | calculated; Generated case-insensitive field-name key used by ASC and DIP. |
| SilkShow | integer | no | no | — | — | stored |
| SilkAlign | integer | no | no | — | — | stored |
| AssyShow | integer | no | no | — | — | stored |
| AssyAlign | integer | no | no | — | — | stored |

## PcbGlobalUserFields

| Child | Record type | Count |
| --- | --- | --- |
| UserField | [PcbGlobalUserField](#pcbglobaluserfield) | 0..many |

## PcbGroup

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Id | integer | no | no | — | — | calculated |
| Enabled | boolean | no | no | `False` | — | stored |
| Selected | boolean | no | no | `False` | — | stored |
| X | number | no | no | `0` | shared length | stored |
| Y | number | no | no | `0` | shared length | stored |

## PcbGroups

| Child | Record type | Count |
| --- | --- | --- |
| Group | [PcbGroup](#pcbgroup) | 0..many |

## PcbHoles

| Child | Record type | Count |
| --- | --- | --- |
| Hole | [Hole](#hole) | 0..many |

## PcbInternalConnectionDefinition

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Pad1 | reference | no | yes | — | — | relationship |
| Pad2 | reference | no | yes | — | — | relationship |
| X | integer | no | no | — | — | calculated |
| Y | integer | no | no | — | — | calculated |

## PcbInternalConnectionDefinitions

| Child | Record type | Count |
| --- | --- | --- |
| Item | [PcbInternalConnectionDefinition](#pcbinternalconnectiondefinition) | 0..many |

## PcbInternalConnectionPolicies

| Child | Record type | Count |
| --- | --- | --- |
| IntCon | [PcbInternalConnectionPolicy](#pcbinternalconnectionpolicy) | 0..many |

## PcbInternalConnectionPolicy

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Pad | reference | no | yes | — | — | relationship; A member selecting the connected group. Serialization preserves the group policy; the representative member can be canonicalized when reading a file. |
| ConnectAll | boolean | no | no | `False` | — | stored |
| Id | integer | no | no | — | — | calculated |
| Members | tuple | no | yes | — | — | calculated |
| ↳ items | reference | — | — | — | — | variable items |
| Ratlines | tuple | no | yes | — | — | calculated |
| ↳ items | tuple | — | — | — | — | variable items |

## PcbLayerClearance

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Layer | reference | no | yes | — | — | relationship |
| Lay | integer | no | no | — | — | calculated |
| Clearance | number | no | yes | `None` | shared length | stored |

## PcbLayerClearances

| Child | Record type | Count |
| --- | --- | --- |
| LayerClearance | [PcbLayerClearance](#pcblayerclearance) | 0..many |

## PcbLayerMaterial

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Name | text | no | no | `''` | — | stored |
| Type | integer | no | no | — | — | calculated; Conductor/plane follows the copper layer; an item without a copper layer is dielectric. |
| VariableThickness | boolean | no | no | `False` | — | stored |
| Constant | number | no | no | `0` | — | stored |
| Thickness | number | no | no | `0` | shared length | stored |
| TraceWidth | number | no | no | `0` | shared length | stored |

## PcbLayerPanel

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| TopAssy | boolean | no | no | — | — | stored |
| TopMask | boolean | no | no | — | — | stored |
| TopPaste | boolean | no | no | — | — | stored |
| BotAssy | boolean | no | no | — | — | stored |
| BotMask | boolean | no | no | — | — | stored |
| BotPaste | boolean | no | no | — | — | stored |
| Board | boolean | no | no | — | — | stored |
| TopTerminals | boolean | no | no | — | — | stored |
| BotTerminals | boolean | no | no | — | — | stored |
| TopCourtyard | boolean | no | no | — | — | stored |
| BotCourtyard | boolean | no | no | — | — | stored |
| TopOutline | boolean | no | no | — | — | stored |
| BotOutline | boolean | no | no | — | — | stored |
| TopDimensions | boolean | no | no | — | — | stored |
| BotDimensions | boolean | no | no | — | — | stored |

## PcbLayerStackItem

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Id | integer | no | no | — | — | calculated |
| Layer | reference | no | yes | — | — | relationship |
| Lay | integer | no | no | — | — | calculated |

| Child | Record type | Count |
| --- | --- | --- |
| Material | [PcbLayerMaterial](#pcblayermaterial) | 1..1 |

## PcbLayerStackItems

| Child | Record type | Count |
| --- | --- | --- |
| LayerStackItem | [PcbLayerStackItem](#pcblayerstackitem) | 0..many |

## PcbLengthConnection

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Net | reference | no | yes | — | — | relationship |
| NetId | integer | no | no | — | — | calculated |
| Pad1 | reference | no | yes | — | — | relationship |
| Component1 | reference | no | yes | — | — | calculated |
| ComponentIndex1 | integer | no | no | — | — | calculated |
| PadIndex1 | integer | no | no | — | — | calculated |
| Pad2 | reference | no | yes | — | — | relationship |
| Component2 | reference | no | yes | — | — | calculated |
| ComponentIndex2 | integer | no | no | — | — | calculated |
| PadIndex2 | integer | no | no | — | — | calculated |
| Length | number | no | no | `0` | shared length | stored |
| Error | boolean | no | no | `False` | — | stored |

## PcbLengthConnections

| Child | Record type | Count |
| --- | --- | --- |
| Rule | [PcbLengthConnection](#pcblengthconnection) | 0..many |

## PcbLengthRule

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Name | text | no | no | `''` | — | stored |
| FixedLength | number | no | no | `-1` | shared length | stored |
| Delta | number | no | no | `Decimal('7.62')` | shared length | stored |
| AnyError | boolean | no | no | — | — | calculated; Aggregate of the stored connection error results; does not calculate route length. |
| Class | reference | no | yes | — | — | relationship; Optional class selection of MainLengthRule; its working name, limits and connections remain independent. |
| NetClass | integer | no | no | — | — | calculated |

| Child | Record type | Count |
| --- | --- | --- |
| Rules | [PcbLengthConnections](#pcblengthconnections) | 0..1 |

## PcbLengthRules

| Child | Record type | Count |
| --- | --- | --- |
| LengthRule | [PcbLengthRule](#pcblengthrule) | 0..many |

## PcbLocalGroup

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Enabled | boolean | yes | no | `True` | — | stored |
| Id | integer | no | no | — | — | calculated; Calculated local group position. |
| X | number | yes | no | `0` | shared length | stored |
| Y | number | yes | no | `0` | shared length | stored |

## PcbLocalGroups

| Child | Record type | Count |
| --- | --- | --- |
| pt | [PcbLocalGroup](#pcblocalgroup) | 0..many |

## PcbNegativePoints

| Child | Record type | Count |
| --- | --- | --- |
| NegPoint | [PcbPairSidePoint](#pcbpairsidepoint) | 0..many |

## PcbNegativeTraces

| Child | Record type | Count |
| --- | --- | --- |
| NegTrace | [PcbSeparateTrace](#pcbseparatetrace) | 0..many |

## PcbNet

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Class | reference | no | yes | — | — | relationship |
| NetClass | integer | no | no | — | — | calculated |
| Name | text | yes | no | `''` | — | stored |
| Enabled | boolean | yes | no | `True` | — | stored |
| Locked | boolean | no | no | `False` | — | stored |
| HideRatlines | boolean | no | no | `False` | — | stored |
| ShowLength | boolean | no | no | `False` | — | stored |
| CustomColor | boolean | no | no | `False` | — | stored |
| AllowLoops | boolean | no | no | `False` | — | stored |
| Highlighted | boolean | no | no | `False` | — | stored |
| HiddenId | integer | no | no | `-1` | — | stored |
| RouteMode | integer | no | no | `0` | — | stored |
| TraceColor | integer | no | no | `0` | — | stored |
| ActiveLine | integer | no | no | `-1` | — | stored |
| ActivePoint | integer | no | no | `-1` | — | stored |
| Width | number | no | no | `-1` | — | stored |
| Clearance | number | no | no | `-1` | — | stored |
| MeanderGap | number | no | no | `-1` | — | stored |
| Number | integer | no | no | — | — | calculated |

| Child | Record type | Count |
| --- | --- | --- |
| Pads | [PcbNetMembers](#pcbnetmembers) | 1..1 |
| Traces | [PcbTraces](#pcbtraces) | 1..1 |
| TeardropParams | [TeardropParameters](#teardropparameters) | 0..1 |
| Teardrops | [PcbTeardrops](#pcbteardrops) | 0..1 |

## PcbNetClass

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Name | text | yes | no | `''` | — | stored |
| Id | integer | no | no | — | — | calculated |
| Type | integer | no | no | `0` | — | stored |
| HiddenID | integer | no | no | `0` | — | stored |
| PriorityValue | integer | no | no | `0` | — | stored |
| MaxViasValue | integer | no | no | `0` | — | stored |
| AllLayers | boolean | no | no | `False` | — | stored |
| CheckLength | boolean | no | no | `False` | — | stored |
| AllVias | boolean | no | no | `False` | — | stored |
| PerformDRC | boolean | no | no | `False` | — | stored |
| RoutePriority | boolean | no | no | `False` | — | stored |
| RouteMaxVias | boolean | no | no | `False` | — | stored |
| RouteMaxIncorrectWay | boolean | no | no | `False` | — | stored |
| RouteAllLayers | boolean | no | no | `False` | — | stored |
| MaxUncoupledLength | number | no | no | `0` | shared length | stored |
| Tolerance | number | no | no | `0` | shared length | stored |
| Phase | number | no | no | `0` | shared length | stored |
| Phase_ErrorLength | number | no | no | `0` | shared length | stored |
| LengthDelta | number | no | no | `Decimal('7.62')` | shared length | stored |
| FixedLength | number | no | no | `-1` | shared length | stored |
| MaxIncorrectWayValue | number | no | no | `0` | — | stored; Autorouting limit scalar, independent of display length units. |

| Child | Record type | Count |
| --- | --- | --- |
| LayProperties | [PcbClassLayerProperties](#pcbclasslayerproperties) | 0..1 |
| AllowedVias | [PcbAllowedVias](#pcballowedvias) | 0..1 |
| RouteLayers | [PcbRouteLayers](#pcbroutelayers) | 0..1 |
| LengthResults | [PcbClassLengthResults](#pcbclasslengthresults) | 0..1 |

## PcbNetClasses

| Child | Record type | Count |
| --- | --- | --- |
| NetClass | [PcbNetClass](#pcbnetclass) | 0..many |

## PcbNetMember

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Pad | reference | no | no | — | — | calculated; Identity of the placed pad assigned to this net. |
| ComponentIndex | integer | no | no | — | — | calculated |
| PadIndex | integer | no | no | — | — | calculated |

## PcbNetMembers

| Child | Record type | Count |
| --- | --- | --- |
| Item | [PcbNetMember](#pcbnetmember) | 0..many |

## PcbNets

| Child | Record type | Count |
| --- | --- | --- |
| Net | [PcbNet](#pcbnet) | 0..many |

## PcbNonSignalLayer

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Name | text | no | no | `''` | — | stored |
| Id | integer | no | no | — | — | calculated |
| Color | integer | no | no | `0` | — | stored |
| Side | integer | no | no | `0` | — | stored |
| Visible | boolean | no | no | — | — | stored; Optional layer-panel visibility supplied by the document. |

## PcbNonSignalLayers

| Child | Record type | Count |
| --- | --- | --- |
| NonSignal | [PcbNonSignalLayer](#pcbnonsignallayer) | 0..many |

## PcbOutlinePoint

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| X | number | yes | no | `0` | shared length | stored |
| Y | number | yes | no | `0` | shared length | stored |
| Arc | boolean | yes | no | `False` | — | stored |

## PcbOutlinePoints

| Child | Record type | Count |
| --- | --- | --- |
| pt | [PcbOutlinePoint](#pcboutlinepoint) | 0..many |

## PcbPad

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
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
| PadWidth_New | number | yes | yes | — | — | stored; Main copper dimension; None means unavailable geometry. |
| PadHeight_New | number | yes | yes | — | — | stored; Main copper dimension; None means unavailable geometry. |
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
| Net | reference | no | yes | — | — | relationship; Assigned PCB net identity; None disconnects the pad. |
| NetNumber | integer | no | no | — | — | calculated; Calculated net position; edit Net instead. |
| InternalConnection | integer | no | no | — | — | calculated; Calculated connection-group position; labels and authored pairs define membership. |
| ShieldGroup | integer | no | no | `-1` | — | stored |
| SignalDelay | number | no | no | `0` | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| PadMask_TopSegments | [PasteSegments](#pastesegments) | 0..1 |
| PadMask_BotSegments | [PasteSegments](#pastesegments) | 0..1 |
| PadPoints_New | [Points](#points) | 0..1 |
| PadTerminal | [PadTerminal](#padterminal) | 0..many |
| UnresolvedKeys | [UnresolvedKeys](#unresolvedkeys) | 0..1 |
| HideLayer | [HiddenPadLayers](#hiddenpadlayers) | 0..1 |
| BlindLayer | [BlindPadLayers](#blindpadlayers) | 0..1 |
| CustomSpokes | [PadThermals](#padthermals) | 0..1 |
| TeardropParams | [TeardropParameters](#teardropparameters) | 0..1 |

## PcbPadLayer

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Layer | reference | no | yes | — | — | relationship |
| Lay | integer | no | no | — | — | calculated |

## PcbPadThermal

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Layer | reference | no | yes | — | — | relationship |
| Lay | integer | no | no | — | — | calculated |
| Type | integer | no | no | `0` | — | stored |
| Spoke | integer | no | no | `0` | — | stored |
| Width | number | no | no | `0` | shared length | stored |

## PcbPads

| Child | Record type | Count |
| --- | --- | --- |
| Pad | [PcbPad](#pcbpad) | 0..many |

## PcbPairCenter

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Id | integer | no | no | — | — | calculated |
| Layer | reference | no | yes | — | — | relationship |
| Lay | integer | no | no | — | — | calculated |
| Via | reference | no | yes | — | — | relationship |
| ViaStyle | integer | no | no | — | — | calculated |
| X | number | yes | no | `0` | shared length | stored |
| Y | number | yes | no | `0` | shared length | stored |
| Type | integer | no | no | `0` | — | stored |
| PosTraceSide | integer | no | no | `-1` | — | stored |
| PosShieldGroup | integer | no | no | `-1` | — | stored |
| NegShieldGroup | integer | no | no | `-1` | — | stored |
| PosStartPoint | reference | no | yes | — | — | relationship |
| PosTrace_StartPoint | integer | no | no | — | — | calculated |
| UnresolvedPosStartPointIndex | integer | no | no | — | — | stored; An unavailable current range-point selection. |
| PosEndPoint | reference | no | yes | — | — | relationship |
| PosTrace_EndPoint | integer | no | no | — | — | calculated |
| UnresolvedPosEndPointIndex | integer | no | no | — | — | stored; An unavailable current range-point selection. |
| NegStartPoint | reference | no | yes | — | — | relationship |
| NegTrace_StartPoint | integer | no | no | — | — | calculated |
| UnresolvedNegStartPointIndex | integer | no | no | — | — | stored; An unavailable current range-point selection. |
| NegEndPoint | reference | no | yes | — | — | relationship |
| NegTrace_EndPoint | integer | no | no | — | — | calculated |
| UnresolvedNegEndPointIndex | integer | no | no | — | — | stored; An unavailable current range-point selection. |
| Necked | boolean | no | no | `False` | — | stored |
| Selected | boolean | no | no | `False` | — | stored |
| PhaseError | boolean | no | no | `False` | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| PosPoints | [PcbPositivePoints](#pcbpositivepoints) | 0..1 |
| NegPoints | [PcbNegativePoints](#pcbnegativepoints) | 0..1 |

## PcbPairCenters

| Child | Record type | Count |
| --- | --- | --- |
| CenterPoint | [PcbPairCenter](#pcbpaircenter) | 0..many |

## PcbPairSegment

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Id | integer | no | no | — | — | calculated |
| Start | reference | no | yes | — | — | relationship |
| StartPoint | integer | no | no | — | — | calculated |
| StartSegment | integer | no | no | — | — | calculated |
| End | reference | no | yes | — | — | relationship |
| EndPoint | integer | no | no | — | — | calculated |
| EndSegment | integer | no | no | — | — | calculated |
| PosTrace | reference | no | yes | — | — | relationship |
| PosTraceIndex | integer | no | no | — | — | calculated |
| NegTrace | reference | no | yes | — | — | relationship |
| NegTraceIndex | integer | no | no | — | — | calculated |

| Child | Record type | Count |
| --- | --- | --- |
| CenterPoints | [PcbPairCenters](#pcbpaircenters) | 1..1 |

## PcbPairSegments

| Child | Record type | Count |
| --- | --- | --- |
| Segment | [PcbPairSegment](#pcbpairsegment) | 0..many |

## PcbPairSidePoint

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Layer | reference | no | yes | — | — | relationship |
| Lay | integer | no | no | — | — | calculated |
| Via | reference | no | yes | — | — | relationship |
| ViaStyle | integer | no | no | — | — | calculated |
| Id | integer | no | no | — | — | calculated |
| X | number | yes | no | `0` | shared length | stored |
| Y | number | yes | no | `0` | shared length | stored |
| Meander | integer | no | no | `0` | — | stored |
| ShieldGroup | integer | no | no | `-1` | — | stored |
| Arc | boolean | no | no | `False` | — | stored |
| Selected | boolean | no | no | `False` | — | stored |
| MeanderAngle | number | no | no | `0` | — | stored |
| Necked | boolean | no | no | `False` | — | stored |

## PcbPairedPad

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Id | integer | no | no | — | — | calculated |
| PosPad | reference | no | yes | — | — | relationship |
| PosComponentIndex | integer | no | no | — | — | calculated |
| PosPadIndex | integer | no | no | — | — | calculated |
| NegPad | reference | no | yes | — | — | relationship |
| NegComponentIndex | integer | no | no | — | — | calculated |
| NegPadIndex | integer | no | no | — | — | calculated |

## PcbPairedPads

| Child | Record type | Count |
| --- | --- | --- |
| PadPoint | [PcbPairedPad](#pcbpairedpad) | 0..many |

## PcbPanel

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Type | integer | no | no | — | — | stored |
| BorderTabs | integer | no | no | — | — | stored |
| TabsDone | boolean | no | no | — | — | stored |
| KeepMaterial | boolean | no | no | — | — | stored |
| PanelizeSingle | boolean | no | no | — | — | stored |
| TabWidth | number | no | no | — | shared length | stored |
| TabRadius | number | no | no | — | shared length | stored |
| TabStep | number | no | no | — | shared length | stored |
| HoleDiam | number | no | no | — | shared length | stored |
| HoleStep | number | no | no | — | shared length | stored |
| HoleInset | number | no | no | — | shared length | stored |
| HoleKeepout | number | no | no | — | shared length | stored |
| CombinedRadius | number | no | no | — | shared length | stored |
| LeftGap | number | no | no | — | shared length | stored |
| RightGap | number | no | no | — | shared length | stored |
| TopGap | number | no | no | — | shared length | stored |
| BottomGap | number | no | no | — | shared length | stored |

| Child | Record type | Count |
| --- | --- | --- |
| HorzTabsX | [PcbPanelTabPositions](#pcbpaneltabpositions) | 0..1 |
| VertTabsY | [PcbPanelTabPositions](#pcbpaneltabpositions) | 0..1 |

## PcbPanelTabPosition

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Position | number | yes | no | — | shared length | stored |

## PcbPanelTabPositions

| Child | Record type | Count |
| --- | --- | --- |
| Item | [PcbPanelTabPosition](#pcbpaneltabposition) | 0..many |

## PcbPattern

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
| Pattern_Manufacturer | text | no | no | — | — | stored |
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
| Pads | [PcbPads](#pcbpads) | 0..1 |
| Shapes | [PcbPatternDrawings](#pcbpatterndrawings) | 0..1 |
| Holes | [PcbHoles](#pcbholes) | 0..1 |
| Dimensions | [PcbPatternDimensions](#pcbpatterndimensions) | 0..1 |
| Model3D | [Model3D](#model3d) | 0..1 |
| PadPoints | [Points](#points) | 0..1 |
| PadTerminal | [PadTerminal](#padterminal) | 0..many |

## PcbPatternDimension

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

## PcbPatternDimensions

| Child | Record type | Count |
| --- | --- | --- |
| Dimension | [PcbPatternDimension](#pcbpatterndimension) | 0..many |

## PcbPatternDrawing

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
| PadId | integer | no | no | — | — | calculated |
| Index | integer | yes | no | `0` | — | calculated |
| Pad | reference | no | yes | — | — | relationship |
| MarkingGenerated | boolean | no | no | `False` | — | stored |
| ShieldGroup | integer | no | no | `-1` | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| Points_New | [Points](#points) | 0..1 |
| TextLine | [TextLines](#textlines) | 0..1 |
| UnresolvedKeys | [UnresolvedKeys](#unresolvedkeys) | 0..1 |

## PcbPatternDrawings

| Child | Record type | Count |
| --- | --- | --- |
| Shape | [PcbPatternDrawing](#pcbpatterndrawing) | 0..many |

## PcbPositivePoints

| Child | Record type | Count |
| --- | --- | --- |
| PosPoint | [PcbPairSidePoint](#pcbpairsidepoint) | 0..many |

## PcbPositiveTraces

| Child | Record type | Count |
| --- | --- | --- |
| PosTrace | [PcbSeparateTrace](#pcbseparatetrace) | 0..many |

## PcbPourFill

| Child | Record type | Count |
| --- | --- | --- |
| Lines | [PcbFillLines](#pcbfilllines) | 0..1 |
| SpokeLine | [PcbSpokeLines](#pcbspokelines) | 0..1 |
| Polygons | [PcbFillPolygons](#pcbfillpolygons) | 0..1 |
| Regions | [PcbPourRegions](#pcbpourregions) | 0..1 |

## PcbPourRegion

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Number | integer | yes | no | `0` | — | stored; Nonnegative classification label, unique within this fill. |

## PcbPourRegions

Available calculated classification; absence means unavailable, including when fill geometry exists.

| Child | Record type | Count |
| --- | --- | --- |
| Region | [PcbPourRegion](#pcbpourregion) | 0..many |

## PcbRatline

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Id | integer | no | no | — | — | calculated |
| Enabled | boolean | no | no | `True` | — | stored |
| Hidden | boolean | no | no | `False` | — | stored |
| X1 | number | no | no | `0` | shared length | stored |
| Y1 | number | no | no | `0` | shared length | stored |
| X2 | number | no | no | `0` | shared length | stored |
| Y2 | number | no | no | `0` | shared length | stored |
| Pad1 | reference | no | yes | — | — | relationship |
| Component1 | reference | no | yes | — | — | calculated |
| ComponentIndex1 | integer | no | no | — | — | calculated |
| PadIndex1 | integer | no | no | — | — | calculated |
| Pad2 | reference | no | yes | — | — | relationship |
| Component2 | reference | no | yes | — | — | calculated |
| ComponentIndex2 | integer | no | no | — | — | calculated |
| PadIndex2 | integer | no | no | — | — | calculated |

## PcbRatlines

| Child | Record type | Count |
| --- | --- | --- |
| Ratline | [PcbRatline](#pcbratline) | 0..many |

## PcbRemovedDifferentialPair

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Class | reference | no | yes | — | — | relationship |
| NetClass | integer | no | no | — | — | calculated |
| Id | integer | no | no | — | — | calculated |
| Name | text | no | no | `''` | — | stored |
| Enabled | boolean | no | no | `True` | — | stored |
| CustomColor | boolean | no | no | `False` | — | stored |
| TraceColor | integer | no | no | `0` | — | stored |
| PosNet | reference | no | yes | — | — | relationship |
| NegNet | reference | no | yes | — | — | relationship |
| PosNetIndex | integer | no | no | — | — | calculated |
| NegNetIndex | integer | no | no | — | — | calculated |

| Child | Record type | Count |
| --- | --- | --- |
| PadPoints | [PcbPairedPads](#pcbpairedpads) | 0..1 |
| Segments | [PcbPairSegments](#pcbpairsegments) | 0..1 |

## PcbRemovedDifferentialPairs

| Child | Record type | Count |
| --- | --- | --- |
| RemovedDifferentialPair | [PcbRemovedDifferentialPair](#pcbremoveddifferentialpair) | 0..many |

## PcbRouteLayer

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Layer | reference | no | yes | — | — | relationship |
| Lay | integer | no | no | — | — | calculated |
| Enabled | boolean | no | no | `True` | — | stored |

## PcbRouteLayers

| Child | Record type | Count |
| --- | --- | --- |
| Item | [PcbRouteLayer](#pcbroutelayer) | 0..many |

## PcbRoutingSettings

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| TraceWidth | number | no | yes | — | shared length | relationship |
| TraceClearance | number | no | yes | — | shared length | relationship |
| PadClearance | number | no | no | `0` | shared length | stored |
| BoardClearance | number | no | no | `0` | shared length | stored |
| ViaSize | number | no | no | `0` | shared length | stored |
| FanoutLength | number | no | no | `0` | shared length | stored |
| ViaHole | number | no | no | `0` | shared length | stored |
| Router | integer | no | no | `0` | — | stored |
| ViaApply | integer | no | no | `0` | — | stored |

## PcbSeparateTrace

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Id | integer | no | no | — | — | calculated |
| Target1 | reference | no | yes | — | — | relationship |
| Connected1 | text | no | no | — | — | calculated |
| Object1 | integer | no | no | — | — | calculated |
| SubObject1 | integer | no | no | — | — | calculated |
| Point1 | integer | no | no | — | — | calculated |
| Target2 | reference | no | yes | — | — | relationship |
| Connected2 | text | no | no | — | — | calculated |
| Object2 | integer | no | no | — | — | calculated |
| SubObject2 | integer | no | no | — | — | calculated |
| Point2 | integer | no | no | — | — | calculated |
| Selected | boolean | no | no | `False` | — | stored |
| Group | reference | no | yes | — | — | relationship |
| GroupId | integer | no | no | — | — | calculated |
| NetTrace | reference | no | yes | — | — | relationship |
| TraceId | integer | no | no | — | — | calculated |

| Child | Record type | Count |
| --- | --- | --- |
| Points | [PcbTracePoints](#pcbtracepoints) | 1..1 |

## PcbSettings

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| GridEnabled | boolean | no | no | — | — | stored |
| GridSnap | boolean | no | no | — | — | stored |
| YGridIdentical | boolean | no | no | — | — | stored |
| OriginEnabled | boolean | no | no | — | — | stored |
| FlipTextAuto | boolean | no | no | — | — | stored |
| AssyPads | boolean | no | no | — | — | stored |
| AssySilk | boolean | no | no | — | — | stored |
| AssyPatBorders | boolean | no | no | — | — | stored |
| AssyBoardOutline | boolean | no | no | — | — | stored |
| EditInactiveLayer | boolean | no | no | — | — | stored |
| StackLength | boolean | no | no | — | — | stored |
| SignalDelayLength | boolean | no | no | — | — | stored |
| ShowCompFiducials | boolean | no | no | — | — | stored |
| AxisColor | integer | no | no | — | — | stored |
| JumperLayer | integer | no | no | — | — | stored |
| LayerDisplayMode | integer | no | no | — | — | stored |
| GridSize | number | no | no | — | shared length | stored |
| YGridSize | number | no | no | — | shared length | stored |
| SilkLineWidth | number | no | no | — | shared length | stored |
| TableLineWidth | number | no | no | — | shared length | stored |
| TitlesLineWidth | number | no | no | — | shared length | stored |
| BoardOutlineWidth | number | no | no | — | shared length | stored |
| AssemblyWidth | number | no | no | — | shared length | stored |
| CompOutlineWidth | number | no | no | — | shared length | stored |
| CourtyardWidth | number | no | no | — | shared length | stored |
| SolderMaskSwell | number | no | no | — | shared length | stored |
| PasteMaskShrink | number | no | no | — | shared length | stored |

| Child | Record type | Count |
| --- | --- | --- |
| Routing | [PcbRoutingSettings](#pcbroutingsettings) | 0..1 |
| LayerPanel | [PcbLayerPanel](#pcblayerpanel) | 0..1 |

## PcbSheetSettings

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| SheetWidth | number | no | no | — | shared length | stored |
| SheetHeight | number | no | no | — | shared length | stored |
| LeftMargin | number | no | no | — | shared length | stored |
| TopMargin | number | no | no | — | shared length | stored |
| RightMargin | number | no | no | — | shared length | stored |
| BottomMargin | number | no | no | — | shared length | stored |
| DisplayTitles | boolean | no | no | — | — | stored |
| DisplaySheet | boolean | no | no | — | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| BorderZones | [PcbBorderZones](#pcbborderzones) | 0..1 |
| TitleBlocks | [PcbTitleBlocks](#pcbtitleblocks) | 0..1 |

## PcbSpokeLine

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| X1 | number | no | no | `0` | shared length | stored |
| Y1 | number | no | no | `0` | shared length | stored |
| X2 | number | no | no | `0` | shared length | stored |
| Y2 | number | no | no | `0` | shared length | stored |
| Region | reference | no | yes | — | — | relationship |
| RegionId | integer | no | no | — | — | calculated; Current group label, or -1 when unassigned; edit Region instead. |
| Width | number | no | no | `0` | shared length | stored |

## PcbSpokeLines

| Child | Record type | Count |
| --- | --- | --- |
| Line | [PcbSpokeLine](#pcbspokeline) | 0..many |

## PcbTable

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Id | integer | no | no | — | — | calculated |
| Group | reference | no | yes | — | — | relationship |
| GroupId | integer | no | no | — | — | calculated |
| Enabled | boolean | no | no | `False` | — | stored |
| Selected | boolean | no | no | `False` | — | stored |
| Locked | boolean | no | no | `False` | — | stored |
| DefVectorFont | boolean | no | no | `False` | — | stored |
| HideBorder | boolean | no | no | `False` | — | stored |
| PanelExclude | boolean | no | no | `False` | — | stored |
| DefFontMono | boolean | no | no | `False` | — | stored |
| Layer | integer | no | no | `0` | — | stored |
| DefAlign | integer | no | no | `0` | — | stored |
| Orientation | integer | no | no | `0` | — | stored |
| DefFontColor | integer | no | no | `0` | — | stored |
| DocType | integer | no | no | `0` | — | stored |
| DocUnits | integer | no | no | `0` | — | stored |
| NonSignalLayer | reference | no | yes | — | — | relationship |
| NonSignal | integer | no | no | — | — | calculated |
| UnresolvedNonSignal | integer | no | no | — | — | stored |
| DefFontSize | number | no | no | `0` | — | stored |
| DefCellWidth | number | no | no | `0` | — | stored |
| DefCellHeight | number | no | no | `0` | — | stored |
| X1 | number | no | no | `0` | — | stored |
| Y1 | number | no | no | `0` | — | stored |
| X2 | number | no | no | `0` | — | stored |
| Y2 | number | no | no | `0` | — | stored |
| DefFontWidth | number | no | no | `0` | — | stored |
| DefFontScale | number | no | no | `0` | — | stored |
| DefLineSpacing | number | no | no | `0` | — | stored |
| DefFontName | text | no | no | `''` | — | stored |
| Name | text | no | no | `''` | — | stored |
| Supplier | text | no | no | `''` | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| Cells | [TableCells](#tablecells) | 0..1 |
| ColWidths | [ColumnWidths](#columnwidths) | 0..1 |
| RowHeights | [RowHeights](#rowheights) | 0..1 |
| AutoUpdate | [PcbTableUpdate](#pcbtableupdate) | 0..1 |
| RowComponents | [PcbTableComponentRows](#pcbtablecomponentrows) | 0..1 |

## PcbTableComponentRow

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Index | integer | no | no | — | — | calculated |

| Child | Record type | Count |
| --- | --- | --- |
| Item | [PcbTableRowComponent](#pcbtablerowcomponent) | 0..many |

## PcbTableComponentRows

| Child | Record type | Count |
| --- | --- | --- |
| Row | [PcbTableComponentRow](#pcbtablecomponentrow) | 0..many |

## PcbTableRowComponent

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Component | reference | no | yes | — | — | relationship |
| ComponentIndex | integer | no | no | — | — | calculated |
| UnresolvedComponentIndex | integer | no | no | — | — | stored; A supplied component position without a current target; absent for resolved members. |

## PcbTableUpdate

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| RowType | integer | no | no | — | — | stored |
| Variant | reference | no | yes | — | — | relationship |
| AssemblyVariant | integer | no | no | — | — | calculated |
| UnresolvedAssemblyVariant | integer | no | no | — | — | stored |
| PickOffX | number | no | no | — | — | stored |
| PickOffY | number | no | no | — | — | stored |
| Header | boolean | no | no | — | — | stored |
| BomRowNumber | boolean | no | no | — | — | stored |
| BomTotal | boolean | no | no | — | — | stored |
| PickMirror | boolean | no | no | — | — | stored |
| PickOrigin | boolean | no | no | — | — | stored |
| AssemblyName | text | no | no | — | — | stored |
| Separator | text | no | no | — | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| Columns | [PcbTableUpdateColumns](#pcbtableupdatecolumns) | 0..1 |

## PcbTableUpdateColumn

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Type | integer | no | no | — | — | stored |
| TextAlign | integer | no | no | — | — | stored |
| Width | number | no | no | — | — | stored |
| Name | text | no | no | `''` | — | stored |
| Title | text | no | no | `''` | — | stored |
| Index | integer | no | no | — | — | calculated |

## PcbTableUpdateColumns

| Child | Record type | Count |
| --- | --- | --- |
| Column | [PcbTableUpdateColumn](#pcbtableupdatecolumn) | 0..many |

## PcbTables

| Child | Record type | Count |
| --- | --- | --- |
| Table | [PcbTable](#pcbtable) | 0..many |

## PcbTeardrop

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Id | integer | no | no | — | — | calculated |
| Layer | reference | no | yes | — | — | relationship |
| Lay | integer | no | no | — | — | calculated |
| DrawX | number | no | no | `0` | shared length | stored |
| DrawY | number | no | no | `0` | shared length | stored |

| Child | Record type | Count |
| --- | --- | --- |
| Points | [Points](#points) | 0..1 |

## PcbTeardrops

| Child | Record type | Count |
| --- | --- | --- |
| Teardrop | [PcbTeardrop](#pcbteardrop) | 0..many |

## PcbTitleBlock

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Position | integer | no | no | — | — | calculated; 0 BottomRight, 1 BottomLeft, 2 TopRight, 3 TopLeft, 4 ExtTopLeft, 5 ExtBottomLeft. |
| Name | text | yes | no | `''` | — | stored |
| Width | number | yes | no | `0` | shared length | stored |
| Height | number | yes | no | `0` | shared length | stored |

| Child | Record type | Count |
| --- | --- | --- |
| Cells | [PcbTitleCells](#pcbtitlecells) | 0..1 |
| Contents | [PcbTitleFields](#pcbtitlefields) | 0..1 |
| ColWidths | [ColumnWidths](#columnwidths) | 0..1 |
| RowHeights | [RowHeights](#rowheights) | 0..1 |

## PcbTitleBlocks

| Child | Record type | Count |
| --- | --- | --- |
| TitleBlock | [PcbTitleBlock](#pcbtitleblock) | 0..6 |

## PcbTitleCell

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Column | integer | no | no | — | — | calculated; Zero-based column in its containing grid. |
| Row | integer | no | no | — | — | calculated; Zero-based row in its containing grid. |
| FieldId | integer | no | no | — | — | calculated |
| Edges | tuple | yes | no | — | — | stored |
| ↳ TopLine | boolean | yes | no | False | — |  |
| ↳ BottomLine | boolean | yes | no | False | — |  |
| ↳ LeftLine | boolean | yes | no | False | — |  |
| ↳ RightLine | boolean | yes | no | False | — |  |
| Field | reference | no | yes | — | — | relationship |
| UnresolvedFieldId | integer | no | no | — | — | stored; An unavailable supplied title-field selection. |

## PcbTitleCells

| Child | Record type | Count |
| --- | --- | --- |
| Cell | [PcbTitleCell](#pcbtitlecell) | 0..many |

## PcbTitleFields

| Child | Record type | Count |
| --- | --- | --- |
| Content | [TitleField](#titlefield) | 0..many |

## PcbTrace

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Id | integer | no | no | — | — | calculated |
| Target1 | reference | no | yes | — | — | relationship |
| Connected1 | text | no | no | — | — | calculated |
| Object1 | integer | no | no | — | — | calculated |
| SubObject1 | integer | no | no | — | — | calculated |
| Point1 | integer | no | no | — | — | calculated |
| Target2 | reference | no | yes | — | — | relationship |
| Connected2 | text | no | no | — | — | calculated |
| Object2 | integer | no | no | — | — | calculated |
| SubObject2 | integer | no | no | — | — | calculated |
| Point2 | integer | no | no | — | — | calculated |
| Selected | boolean | no | no | `False` | — | stored |
| Group | reference | no | yes | — | — | relationship |
| GroupId | integer | no | no | — | — | calculated |
| SeparateTrace | reference | no | yes | — | — | calculated |
| PairSeparateTrace | integer | no | no | — | — | calculated |

| Child | Record type | Count |
| --- | --- | --- |
| Points | [PcbTracePoints](#pcbtracepoints) | 1..1 |
| ConnectedTeardrops | [PcbTraceTeardrops](#pcbtraceteardrops) | 0..1 |

## PcbTracePoint

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Layer | reference | no | yes | — | — | relationship |
| Lay | integer | no | no | — | — | calculated |
| Via | reference | no | yes | — | — | relationship |
| ViaStyle | integer | no | no | — | — | calculated |
| Id | integer | no | no | — | — | calculated |
| X | number | yes | no | `0` | shared length | stored |
| Y | number | yes | no | `0` | shared length | stored |
| Width | number | no | no | `-1` | shared length | stored |
| Jumper | integer | no | no | `0` | — | stored |
| Meander | integer | no | no | `0` | — | stored |
| ShieldGroup | integer | no | no | `-1` | — | stored |
| PairTarget | reference | no | yes | — | — | relationship |
| PairPoint | integer | no | no | — | — | calculated |
| PairSubPoint | integer | no | no | — | — | calculated |
| Arc | boolean | no | no | `False` | — | stored |
| Selected | boolean | no | no | `False` | — | stored |
| PairNecked | boolean | no | no | `False` | — | stored |
| PhaseFwd | number | no | yes | `None` | shared length | stored; Calculated phase length, absent when unavailable. |
| PhaseBack | number | no | yes | `None` | shared length | stored; Calculated phase length, absent when unavailable. |
| MeanderAngle | number | no | no | `0` | — | stored |

## PcbTracePoints

| Child | Record type | Count |
| --- | --- | --- |
| Point | [PcbTracePoint](#pcbtracepoint) | 0..many |

## PcbTraceTeardrop

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Teardrop | reference | no | yes | — | — | relationship |
| Index | integer | no | no | — | — | calculated |

## PcbTraceTeardrops

| Child | Record type | Count |
| --- | --- | --- |
| Item | [PcbTraceTeardrop](#pcbtraceteardrop) | 0..many |

## PcbTraces

| Child | Record type | Count |
| --- | --- | --- |
| Trace | [PcbTrace](#pcbtrace) | 0..many |

## PcbUnresolvedCheckTarget

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Object | integer | no | no | — | — | stored |
| SubObject | integer | no | no | — | — | stored |
| Point | integer | no | no | — | — | stored |
| ExtObject | integer | no | no | — | — | stored |

## PcbUserField

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Name | text | yes | no | `''` | — | stored; User-visible field name. |
| Value | text | yes | no | `''` | — | stored; Field text or link. |
| Type | integer | yes | no | `0` | — | stored; 0 Text, 1 Link. |
| SilkShow | integer | no | no | `0` | — | stored |
| SilkAlign | integer | no | no | `0` | — | stored |
| SilkHorz | integer | no | no | `0` | — | stored |
| SilkVert | integer | no | no | `0` | — | stored |
| SilkX | number | no | no | `0` | shared length | stored |
| SilkY | number | no | no | `0` | shared length | stored |
| SilkAngle | number | no | no | `0` | radians | stored |
| AssyShow | integer | no | no | `0` | — | stored |
| AssyAlign | integer | no | no | `0` | — | stored |
| AssyHorz | integer | no | no | `0` | — | stored |
| AssyVert | integer | no | no | `0` | — | stored |
| AssyX | number | no | no | `0` | shared length | stored |
| AssyY | number | no | no | `0` | shared length | stored |
| AssyAngle | number | no | no | `0` | radians | stored |

## PcbUserFields

| Child | Record type | Count |
| --- | --- | --- |
| UserField | [PcbUserField](#pcbuserfield) | 0..many |

## PcbVectorPicture

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Width | number | no | no | `0` | — | stored |
| Height | number | no | no | `0` | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| Polygons | [PcbVectorPolygons](#pcbvectorpolygons) | 0..1 |

## PcbVectorPoint

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Id | integer | no | no | — | — | calculated |
| X | number | yes | no | `0` | shared length | stored |
| Y | number | yes | no | `0` | shared length | stored |

## PcbVectorPoints

| Child | Record type | Count |
| --- | --- | --- |
| Item | [PcbVectorPoint](#pcbvectorpoint) | 0..many |

## PcbVectorPolygon

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Id | integer | no | no | — | — | calculated |

| Child | Record type | Count |
| --- | --- | --- |
| Points | [PcbVectorPoints](#pcbvectorpoints) | 0..1 |

## PcbVectorPolygons

| Child | Record type | Count |
| --- | --- | --- |
| Polygon | [PcbVectorPolygon](#pcbvectorpolygon) | 0..many |

## PcbViaStyle

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Name | text | yes | no | `''` | — | stored |
| Id | integer | no | no | — | — | calculated |
| Size | number | yes | no | `0` | shared length | stored |
| HoleSize | number | yes | no | `0` | shared length | stored |
| Span | tuple | no | yes | — | — | relationship; None spans the complete copper stack; a pair of layer identities defines a bounded span. |
| ↳ From | reference | yes | no | — | — |  |
| ↳ To | reference | yes | no | — | — |  |
| ↳ items | value | — | — | — | — | 2 items |
| Through | boolean | no | no | — | — | calculated |
| FromLayer | reference | no | yes | — | — | calculated |
| Lay1 | integer | no | no | — | — | calculated |
| ToLayer | reference | no | yes | — | — | calculated |
| Lay2 | integer | no | no | — | — | calculated |

## PcbViaStyles

| Child | Record type | Count |
| --- | --- | --- |
| ViaStyle | [PcbViaStyle](#pcbviastyle) | 0..many |

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

## SchematicHierarchyBlock

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Id | integer | yes | no | — | — | stored |
| Name | text | yes | no | `''` | — | stored |

## SchematicHierarchyBlocks

| Child | Record type | Count |
| --- | --- | --- |
| UId | [SchematicHierarchyBlock](#schematichierarchyblock) | 0..many |

## SchematicHierarchyPath

| Child | Record type | Count |
| --- | --- | --- |
| Item | [SchematicHierarchyPathItem](#schematichierarchypathitem) | 0..many |

## SchematicHierarchyPathItem

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Id | integer | yes | no | — | — | stored; Referenced schematic hierarchy-block identifier; linked when its block is available. |

## SchematicHierarchySheet

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Name | text | yes | no | `''` | — | stored |
| Number | integer | yes | no | — | — | stored; Linked schematic sheet identifier, independent of PCB order. |

| Child | Record type | Count |
| --- | --- | --- |
| UpdateIds | [SchematicHierarchyBlocks](#schematichierarchyblocks) | 0..1 |

## SchematicHierarchySheets

| Child | Record type | Count |
| --- | --- | --- |
| HSheet | [SchematicHierarchySheet](#schematichierarchysheet) | 0..many |

## Slots

| Child | Record type | Count |
| --- | --- | --- |
| Slot | [LibrarySlot](#libraryslot) | 0..many |

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

## TableCells

An ordered collection of Cell records.

| Child | Record type | Count |
| --- | --- | --- |
| Cell | [Cell](#cell) | 0..many |

## TeardropParameters

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| PadVia | integer | no | no | `0` | — | stored |
| Smd | integer | no | no | `0` | — | stored |
| Trace | integer | no | no | `0` | — | stored |
| TJunc | integer | no | no | `0` | — | stored |
| PadViaWidth | number | no | no | `0` | — | stored |
| PadViaLength | number | no | no | `0` | — | stored |
| SmdWidth | number | no | no | `0` | — | stored |
| SmdLength | number | no | no | `0` | — | stored |
| TraceLength | number | no | no | `0` | — | stored |
| TJuncLength | number | no | no | `0` | — | stored |

## TextLine

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Text | text | yes | no | `''` | — | stored; Literal text, or calculated content while bound to a component field. |

## TextLines

An ordered collection of TextLine records.

| Child | Record type | Count |
| --- | --- | --- |
| pt | [TextLine](#textline) | 0..many |

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
