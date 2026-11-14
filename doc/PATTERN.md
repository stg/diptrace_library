# Pattern library model reference

Generated from `pattern_schema()`. Use this as a lookup reference; start with the
[getting started](GETTING_STARTED.md), [API reference](API.md) and [model guide](MODEL.md).

Normal LIB, pattern ASC and LIBXML imports share these definitions. Record type names
identify schemas; owned-child names are the names used in paths. Fields hold
values, while children hold records or ordered collections. Tuple members are
named below their field. Reflection returns immutable definitions.

The main hierarchy is `/Library/{Categories,Patterns}`. Each pattern owns
its pads, drawings, holes, dimensions, groups, user fields, internal pad
connections and 3D attachment. Group and local geometry selections refer
to objects in that same pattern. A library entry is a definition rather
than a placed PCB component; it has no net membership or routed traces.

Shared lengths use three units per millimetre. Unspecified units and enum
meanings are left unspecified rather than inferred from field names. Descriptions
list established enum meanings; other typed compatibility values remain valid.
Pad angles use radians. Drawing, terminal and 3D angles have their own
documented units; footprint geometry is not quantized to quarter turns.

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

[CatalogCategory](#catalogcategory) · [CatalogSubtype](#catalogsubtype) · [CatalogType](#catalogtype) · [Categories](#categories) · [InternalConnections](#internalconnections) · [LibraryClassification](#libraryclassification) · [LibraryClassifications](#libraryclassifications) · [LibraryDimension](#librarydimension) · [LibraryDimensions](#librarydimensions) · [LibraryHole](#libraryhole) · [LibraryHoles](#libraryholes) · [LibraryPad](#librarypad) · [LibraryPads](#librarypads) · [LibraryPatternDrawing](#librarypatterndrawing) · [LibraryPatternDrawings](#librarypatterndrawings) · [Model3D](#model3d) · [ModelOffset](#modeloffset) · [ModelRotate](#modelrotate) · [ModelZoom](#modelzoom) · [PadTerminal](#padterminal) · [PasteSegment](#pastesegment) · [PasteSegments](#pastesegments) · [Pattern](#pattern) · [PatternDocument](#patterndocument) · [PatternInternalConnection](#patterninternalconnection) · [PatternLibrary](#patternlibrary) · [PatternLocalGroup](#patternlocalgroup) · [PatternLocalGroups](#patternlocalgroups) · [Patterns](#patterns) · [Point](#point) · [Points](#points) · [PossibleName](#possiblename) · [PossibleNames](#possiblenames) · [Prices](#prices) · [Quote](#quote) · [Suppliers](#suppliers) · [TextLine](#textline) · [TextLines](#textlines) · [UnresolvedKey](#unresolvedkey) · [UnresolvedKeys](#unresolvedkeys) · [UserField](#userfield) · [UserFields](#userfields)

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

## InternalConnections

| Child | Record type | Count |
| --- | --- | --- |
| IntCon | [PatternInternalConnection](#patterninternalconnection) | 0..many |

## LibraryClassification

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Type | text | yes | no | `''` | — | relationship; Classification type name. |
| SubType | text | yes | no | `''` | — | relationship; Classification subtype name. |
| TypeIndex | integer | yes | no | `-1` | — | relationship; Declared type key. |
| SubTypeIndex | integer | yes | no | `-1` | — | relationship; Declared subtype key. |
| TypeDefinition | reference | no | yes | — | — | relationship; Selected catalogue definition; its declared key and label stay coordinated. |
| SubTypeDefinition | reference | no | yes | — | — | relationship; Selected catalogue definition; its declared key and label stay coordinated. |

## LibraryClassifications

An ordered collection of CategoryType records.

| Child | Record type | Count |
| --- | --- | --- |
| CategoryType | [LibraryClassification](#libraryclassification) | 0..many |

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
| X1 | number | yes | no | — | shared length | stored |
| Y1 | number | yes | no | — | shared length | stored |
| X2 | number | yes | no | — | shared length | stored |
| Y2 | number | yes | no | — | shared length | stored |
| XD | number | yes | no | — | shared length | stored |
| YD | number | yes | no | — | shared length | stored |
| ArrowSize | number | yes | no | — | shared length | stored |
| Units | integer | yes | no | — | — | stored |
| VectorFont | boolean | yes | no | — | — | stored |
| FontName | text | yes | no | — | — | stored |
| FontSize | number | yes | no | — | font size | stored |
| FontScale | number | yes | no | — | ratio | stored |
| FontWidth | number | yes | no | — | shared length | stored; Negative pen/width values are style selections, not physical lengths. |
| ShowUnits | boolean | yes | no | — | — | stored |
| Angle | number | yes | no | — | angle | stored |
| ExternalRadius | number | yes | no | — | selection | stored |
| PointerMode | integer | yes | no | — | — | stored |
| PointerText | text | yes | no | — | — | stored |
| FontMono | boolean | no | no | `False` | — | stored |
| Index | integer | yes | no | `0` | — | calculated |
| Group | reference | no | yes | — | — | relationship |
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

## LibraryPad

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Locked | boolean | yes | no | — | — | stored |
| Sided | boolean | yes | no | — | — | stored |
| DisableTopMask | integer | yes | no | — | — | stored |
| DisableBottomMask | integer | yes | no | — | — | stored |
| DisableTopPaste | integer | yes | no | — | — | stored |
| DisableBottomPaste | integer | yes | no | — | — | stored |
| CustomSwell_New | number | yes | no | — | shared length | stored; Unit-independent selections: -1000. |
| CustomShrink_New | number | yes | no | — | shared length | stored; Unit-independent selections: -1000. |
| PadHole | number | yes | no | — | shared length | stored |
| PadHoleH | number | yes | no | — | shared length | stored |
| PadHoleType | integer | yes | no | — | — | stored |
| SurfacePad | boolean | yes | no | — | — | stored |
| PadShape_New | integer | yes | no | — | — | stored; Pad-shape code: 0 ellipse, 1 obround, 2 rectangle, 3 polygon, 4 D-shape, 5 unnamed, 20 fiducial; other numeric codes remain explicit. |
| PadAngle | number | yes | no | — | radians | stored |
| PadShape_X | number | yes | no | — | shared length | stored |
| PadShape_Y | number | yes | no | — | shared length | stored |
| PadCorner | number | yes | no | — | percent | stored |
| PadWidth_New | number | yes | no | — | shared length | stored |
| PadHeight_New | number | yes | no | — | shared length | stored |
| Standard | boolean | yes | no | — | — | stored |
| PadTerminalCount | integer | no | no | — | — | calculated; Calculated number of current terminal records. |
| PadMask_Percent | number | yes | no | — | percent | stored |
| PadMask_EdgeGap | number | yes | no | — | shared length | stored |
| PadMask_SegmentGap | number | yes | no | — | shared length | stored |
| PadMask_SegmentSide | number | yes | no | — | shared length | stored |
| Index | integer | yes | no | `0` | — | calculated |
| StringNumber | text | yes | no | `''` | — | stored |
| Name | text | yes | no | `''` | — | stored |
| X | number | yes | no | `0` | shared length | stored |
| Y | number | yes | no | `0` | shared length | stored |
| Id | integer | no | no | — | — | calculated; Current one-based public pad key; references use object identity. |
| Group | reference | no | yes | — | — | relationship |
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

## LibraryPatternDrawing

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Type | integer | yes | no | — | — | stored |
| Locked | boolean | yes | no | — | — | stored |
| Layer | integer | yes | no | — | — | stored |
| FontName | text | no | no | — | — | stored |
| VectorFont | boolean | no | no | — | — | stored |
| FontSize | number | no | no | — | font size | stored |
| FontScale | number | no | no | — | ratio | stored |
| FontWidth | number | no | no | — | shared length | stored; Negative pen/width values are style selections, not physical lengths. |
| FontMono | boolean | no | no | — | — | stored |
| TextShow | integer | no | no | — | — | stored |
| Width | number | no | no | — | shared length | stored; Geometric drawing stroke; text uses FontWidth and has no Width.; Negative pen/width values are style selections, not physical lengths. |
| TextAngle | number | no | no | — | radians | stored |
| TextHorz | integer | no | no | — | — | stored |
| TextVert | integer | no | no | — | — | stored |
| TextAlign | integer | no | no | — | — | stored |
| LineSpacing | number | no | no | — | ratio | stored |
| AllLayers | boolean | yes | no | — | — | stored |
| Index | integer | yes | no | `0` | — | calculated |
| Pad | reference | no | yes | — | — | relationship |
| PadId | integer | no | no | — | — | calculated |
| UnresolvedPadId | integer | no | no | — | — | stored |
| Group | reference | no | yes | — | — | relationship |
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

## Model3D

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Model3DFile | text | no | no | `''` | — | stored |
| Model3DFile_Variable | text | no | no | `''` | — | stored |
| Mirror | boolean | no | no | `False` | — | stored |
| NoSearch | boolean | no | no | `False` | — | stored |
| Units | integer | no | no | `0` | — | stored |
| IPC_XOff | number | no | no | `0` | shared length | stored |
| IPC_YOff | number | no | no | `0` | shared length | stored |
| AutoHeight | number | no | no | `0` | shared length | stored |
| AutoColor | integer | no | no | `4934475` | — | stored |
| Type | integer | no | no | `0` | — | stored |
| KeepPins | boolean | no | no | `False` | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| Offset | [ModelOffset](#modeloffset) | 0..1 |
| Rotate | [ModelRotate](#modelrotate) | 0..1 |
| Zoom | [ModelZoom](#modelzoom) | 0..1 |

## ModelOffset

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| X | number | yes | no | `0` | shared length | stored; Model offset on this axis. |
| Y | number | yes | no | `0` | shared length | stored; Model offset on this axis. |
| Z | number | yes | no | `0` | shared length | stored; Model offset on this axis. |

## ModelRotate

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| X | number | yes | no | `0` | angle | stored; Model rotate on this axis. |
| Y | number | yes | no | `0` | angle | stored; Model rotate on this axis. |
| Z | number | yes | no | `0` | angle | stored; Model rotate on this axis. |

## ModelZoom

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| X | number | yes | no | `1` | ratio | stored; Model zoom on this axis. |
| Y | number | yes | no | `1` | ratio | stored; Model zoom on this axis. |
| Z | number | yes | no | `1` | ratio | stored; Model zoom on this axis. |

## PadTerminal

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Index | integer | no | no | — | — | calculated; Current terminal position. |
| Type | integer\|text | yes | no | `0` | — | stored; Terminal shape code or a public text selection, including empty text. |
| Angle | number | yes | no | `0` | angle | stored; Unquantized terminal angle in its public field representation. |
| X | number | yes | no | `0` | shared length | stored |
| Y | number | yes | no | `0` | shared length | stored |
| ShapeWidth | number | yes | no | `0` | shared length | stored |
| ShapeHeight | number | yes | no | `0` | shared length | stored |
| ShapeCorner | number | yes | no | `0` | percent | stored |

| Child | Record type | Count |
| --- | --- | --- |
| ShapePoints | [Points](#points) | 0..1 |

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
| Spacing1 | number | yes | no | — | shared length | stored |
| Spacing2 | number | yes | no | — | shared length | stored |
| Spacing3 | number | yes | no | — | shared length | stored |
| LockProperties | boolean | yes | no | — | — | stored |
| PatternOrientation | number | yes | no | — | orientation | stored |
| Width | number | yes | no | — | shared length | stored |
| Height | number | yes | no | — | shared length | stored |
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
| PadCorner | number | yes | no | — | percent | stored |
| PadShape_X | number | yes | no | — | shared length | stored |
| PadShape_Y | number | yes | no | — | shared length | stored |
| PadWidth | number | yes | no | — | shared length | stored |
| PadHeight | number | yes | no | — | shared length | stored |
| PadShape | integer | yes | no | — | — | stored; Pad-shape code: 0 ellipse, 1 obround, 2 rectangle, 3 polygon, 4 D-shape, 5 unnamed, 20 fiducial; other numeric codes remain explicit. |
| SurfacePad | boolean | yes | no | — | — | stored |
| PadHole | number | yes | no | — | shared length | stored |
| PadHoleH | number | yes | no | — | shared length | stored |
| PadHoleType | integer | yes | no | — | — | stored |
| PadTerminalCount | integer | no | no | — | — | calculated; Calculated number of current terminal records. |
| TopMask_State | integer | yes | no | — | — | stored |
| BotMask_State | integer | yes | no | — | — | stored |
| TopPaste_State | integer | yes | no | — | — | stored |
| BotPaste_State | integer | yes | no | — | — | stored |
| CustomSwell_New | number | yes | no | — | shared length | stored; Unit-independent selections: -1000. |
| CustomShrink_New | number | yes | no | — | shared length | stored; Unit-independent selections: -1000. |
| PadMask_Percent | number | yes | no | — | percent | stored |
| PadMask_EdgeGap | number | yes | no | — | shared length | stored |
| PadMask_SegmentGap | number | yes | no | — | shared length | stored |
| PadMask_SegmentSide | number | yes | no | — | shared length | stored |
| OriginX | number | yes | no | — | shared length | stored |
| OriginY | number | yes | no | — | shared length | stored |
| Mounting | integer | yes | no | — | — | stored |
| Pattern_CategoryName | text | yes | no | — | — | relationship |
| Pattern_CategoryIndex | integer | yes | no | — | — | relationship |
| Datasheet | text | no | no | — | — | stored |
| Sided | boolean | no | no | `False` | — | stored |
| RefDes | text | no | no | — | — | stored |
| Name | text | yes | no | `''` | — | stored |
| Category | reference | no | yes | — | — | relationship; Selected catalogue definition; its declared key and label stay coordinated. |
| Value | text | no | no | — | — | stored; Default value of this unplaced pattern. |
| Verification | tuple | yes | no | `(False, False, False, False)` | — | stored; Four saved pattern verification states. |
| ↳ items | boolean | — | — | — | — | 4 items |

| Child | Record type | Count |
| --- | --- | --- |
| Pattern_CategoryTypes | [LibraryClassifications](#libraryclassifications) | 0..1 |
| PossibleNames | [PossibleNames](#possiblenames) | 0..1 |
| PadMask_TopSegments | [PasteSegments](#pastesegments) | 0..1 |
| PadMask_BotSegments | [PasteSegments](#pastesegments) | 0..1 |
| Pads | [LibraryPads](#librarypads) | 0..1 |
| Shapes | [LibraryPatternDrawings](#librarypatterndrawings) | 0..1 |
| Holes | [LibraryHoles](#libraryholes) | 0..1 |
| Dimensions | [LibraryDimensions](#librarydimensions) | 0..1 |
| UserFields | [UserFields](#userfields) | 0..1 |
| Model3D | [Model3D](#model3d) | 0..1 |
| Pattern_Groups | [PatternLocalGroups](#patternlocalgroups) | 0..1 |
| InternalConnections | [InternalConnections](#internalconnections) | 0..1 |
| PadPoints | [Points](#points) | 0..1 |
| PadTerminal | [PadTerminal](#padterminal) | 0..many |
| Suppliers | [Suppliers](#suppliers) | 0..1 |

## PatternDocument

| Child | Record type | Count |
| --- | --- | --- |
| Library | [PatternLibrary](#patternlibrary) | 1..1 |

## PatternInternalConnection

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Pad1 | reference | no | yes | — | — | relationship |
| X | integer | no | no | — | — | calculated |
| UnresolvedX | integer | no | no | — | — | stored |
| Pad2 | reference | no | yes | — | — | relationship |
| Y | integer | no | no | — | — | calculated |
| UnresolvedY | integer | no | no | — | — | stored |

## PatternLibrary

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Name | text | yes | no | `'Library'` | — | stored |
| Hint | text | yes | no | `'Untitled Library'` | — | stored |

| Child | Record type | Count |
| --- | --- | --- |
| Categories | [Categories](#categories) | 0..1 |
| Patterns | [Patterns](#patterns) | 0..1 |

## PatternLocalGroup

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Enabled | boolean | yes | no | `True` | — | stored |
| Id | integer | no | no | — | — | calculated; Current local group position. |
| X | number | no | no | — | shared length | calculated; Calculated centre of the current member-selection envelope. |
| Y | number | no | no | — | shared length | calculated; Calculated centre of the current member-selection envelope. |

## PatternLocalGroups

| Child | Record type | Count |
| --- | --- | --- |
| pt | [PatternLocalGroup](#patternlocalgroup) | 0..many |

## Patterns

| Child | Record type | Count |
| --- | --- | --- |
| Pattern | [Pattern](#pattern) | 0..many |

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

## Quote

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Quantity | integer | yes | no | `0` | — | stored |
| Price | number | yes | no | `0` | currency | stored; Unit price in the supplier currency. |

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

## TextLine

| Field | Type | Required | Nullable | Default | Unit | Access / meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Text | text | yes | no | `''` | — | stored; Literal text, or calculated content while bound to a component field. |

## TextLines

An ordered collection of TextLine records.

| Child | Record type | Count |
| --- | --- | --- |
| pt | [TextLine](#textline) | 0..many |

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
