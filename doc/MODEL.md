# The data model

Every normal import returns the same schematic `Document`. Its ordered tree
contains records, scalar/tuple fields and collections. Public ASC/DCHXML names
guide field names; serialized positions are adapter details.

The model represents the current design, rather than the history of a loaded
file. It owns meaningful values, identities, unresolved references and ordering.
It does not retain old copies of a fact merely to replay a source file.
All input formats use this structure; an exporter projects it into its own layout.

## Organization

```text
Document
  root
    Schematic
      Pages / Page                     sheets, saved views and title blocks
      Components / Part                placed components
        Pins / Pin
        Shapes / Shape                 symbol graphics and text
        UserFields / UserField
        Pattern                        assigned footprint data
      Nets / Net
        Parts / pt                     ordered pin membership
        Lines / Line / Points / pt     wire geometry
      Buses, PageConnectors             other connectivity records
      Shapes, Tables, Groups           sheet graphics and organization
      Settings                         project choices
      CacheLib                         embedded library definitions
```

This is an ownership outline, not a file layout. Collection names are the names
used in paths; schema record names identify their types. Different drawing
contexts have distinct definitions even when their child name is `Shape`.
The [generated schematic catalogue](SCHEMATIC.md) gives the complete hierarchy,
fields, types, tuple members and child cardinalities. The [API guide](API.md)
describes the operations on these records.

## Field access

| Operation | Rule |
| --- | --- |
| `record[name]` | Read a present field; missing names raise `KeyError`. |
| `record.get(name, default=None)` | Read a field or return the default for any missing name. |
| `record[name] = value` | Validate and edit; equivalent to `record.set(name, value)`. |
| `name in record` | Test presence, including values `0`, `False`, `""` and `None`. |
| `del record[name]` | Remove an optional stored field; missing fields raise `KeyError`. |
| `record.schema.field(name)` | Inspect a declared field's immutable definition. |
| `record.schema.children[name]` | Inspect a declared child's type and cardinality. |
| `record.child(name)` | Navigate a child record or collection; missing children return `None`. |

Unknown writes raise `KeyError`. Invalid types, removal of required fields and
assignment to calculated fields are rejected. Nullable fields can contain
`None`; absence is a separate state. Assigning `None` does not remove a field.
A schema describes which fields are declared; membership tests current presence.
Bracket reads of child containers, including empty collections, raise `TypeError`.
Tuple fields retain their tuple read/write form and also expose named members
through `child()`, for example `part.child("ShowRefDes")["Align"]`.

For an existing component `part`:

```python
part["Value"] = "22k"
datasheet = part.get("Datasheet", "")
if "Datasheet" in part:
    del part["Datasheet"]
definition = part.schema.field("Value")
```

Use named predicates such as `//Part[RefDes="R1"]`. A path beginning
`/Schematic/Components/Part` restricts the search to placed components;
`//Part` also finds cached definitions. `one()` raises `LookupError` unless
exactly one record matches. Positional access remains available to adapters
and source inspection; ordinary field editing does not require it.

### Filtering and reference designators

Use `where=` on queries to compare current fields with ordinary Python
predicates. Placement X/Y filtering tests stored origins, not visible geometry.
`document.refdes(prefix)` provides a live numbered-family view of enabled
physical components across all sheets. RefDes identity is the exact prefix and
trailing ASCII counter: leading zeros do not matter, and a bare prefix means
zero. Authored spelling remains stored. Named edits preflight collisions.
See the [query](API.md#searching) and [RefDes](API.md#reference-designators)
sections for matching, allocation, next/previous modes and multipart rules.

## Ownership and relationships

`/Schematic` owns `Pages`, `Components`, `Nets`, `Buses`, `PageConnectors`,
`Shapes`, `Tables`, `Settings`, `CacheLib` and other project settings.
A placed `Part` owns `Pins`, `Shapes`, `UserFields` and its `Pattern`.
Collections preserve meaningful order. `uid` identifies a particular in-memory
record; a cloned document receives independent record identities and links.

For resolved electrical membership, each net's ordered `Parts/pt` entries
own pin identities (`member["Pin"]`). `pin["Net"]` reads the reverse relationship;
assign another net or `None` to move or disconnect it. The member's component/pin
indices and the pin's `NetNumber` are calculated views, not independent edits.
Dependent copies follow assignment, disconnection and retargeting immediately;
their guards are checked before a relationship changes.
Reordering preserves the target identity. Changes that would contradict an
attached wire are rejected before mutation; coordinated connection editing is
a later layer. Contradictory or unresolved imported occurrences remain explicit
and must be resolved before changing that relationship.

Named component/property edits refresh affected bound text and dependent
references, including chains of copied properties; literal text remains
independent. Bound label content is calculated; edit its source field or select
literal text (`FontType = 0`) before editing its text. Invalid types, ambiguous
keys, dependency cycles and changes that
would reinterpret an existing resolved or unresolved link fail before mutation.
Insertion, movement, reordering and removal update affected reference indices
immediately. Invalid cardinalities, duplicate keys, split attachment segments and
unsafe reference scopes fail before the tree changes.
`document.copy(record, parent=..., fields={...})` copies owned links, remaps
internal targets and keeps external targets. Incoming users still refer to the
original; for example, copying a component does not copy a net's memberships.
Root field overrides are checked against the copied relationships.
`document.remove(record)` discards its owned resolved/unresolved links atomically.
External users and unresolved scopes still block removal; retarget or discard
those links first. Plain `detach()` remains conservative about all linked content.
Ordinary supported edits and output do not require `rebuild()`.
Attaching schematic records and assigning previously unused relationship fields
establish recognized links, including pin membership. Unknown supplied identities
remain explicit unresolved links. Changing a mode that would reinterpret an
existing link requires explicitly discarding or replacing that link first.
`Element.clone()` copies tree content without
its arbitrary graph links; use `Document.clone()` for a complete independent design.
`validate()` audits declared stored types, required fields, ownership and
references without changing design values. Schema `readonly` describes an
unconditional constraint; contextual bindings can also prohibit assignment.
Advanced `rebuild()` also projects compatibility
reference indices; it is not a repair operation.
Advanced `Property` and `Key` links accept named calculated fields as well as
stored fields. Calculated views follow their declared order, collection and
relationship inputs without storing a second authored value.

## Values and schema coverage

Numeric fields accept finite numbers; integer fields reject fractional numbers
and booleans. Shared lengths use three units per millimetre. Adapters convert
physical units and XML's Y direction. Component placement angles use degrees; text/label
angles use radians. Schematic output normalizes angles to supported quarter
turns; footprint and 3D angle domains have separate rules.

`record.schema.fields` provides named definitions, types, defaults, nullable and
required status, units where declared, and calculated/read-only status. Main
component, pin, pattern, pad, drawing, page, net, bus, connector, user-field,
settings and table records have definitions. Label choices, user-field headers,
table/title cells, borders, bounds, drawing points and text rows have named
members. Grid coordinates and title placement come from current collection
order. The [generated catalogue](SCHEMATIC.md) lists the supported record
types, fields, tuple members and ownership. `schematic_schema()` returns the same
immutable definitions without requiring a design instance.
Symbol, sheet and footprint drawings have separate definitions. Historical
orientation/name/point occurrences generated for output are not editable model
fields; use the current angle, text rows and point collection. An empty unit
declaration means the unit is unspecified.
Page title blocks occupy six ordered slots. Their `Position` and grid cells'
`Column`/`Row` are read-only views of that order; cell bounds remain authored data.
The document root exposes `Scale` (percent), `Xpos` and `Ypos`; pages retain their
own saved views. Optional `Schematic.ActiveSheet` follows the selected page's
identity. XML output uses this selection unless the export context overrides it.
Simulator argument groups expose public names such as `StartFrequency` and
`StopFrequency`; values remain text so engineering suffixes and expressions work.
Compatibility vectors can have a declared item type and fixed length without
invented names for unknown members.
Wire and bus points expose `X`, `Y` and `Dir`. Classification rows use
`CategoryType` with `Type`, `SubType`, `TypeIndex` and `SubTypeIndex`; declared
catalog keys remain independent of collection position. `PadTerminalCount` and
terminal `Index` are calculated from the current terminal list.

## Import, export and missing data

Import modernizes supported older representations into current facts, including
established compatibility and geometry upgrades. Import takes one supplied file;
unresolved library or picture references remain data instead of triggering
companion discovery. Source syntax inspection is an explicit separate API view.

Absent optional data remains absent. A nullable property can explicitly contain
`None`; neither state needs a duplicate availability flag. Authored choices and
calculated results are distinct facts: for example, a requested filled pour and
its unavailable calculated geometry need not be conflated. A destination that
requires geometry for a filled state must adapt on export. This principle also
applies to future document families; it does not imply current PCB support.

Export prepares a detached view. It generates bookkeeping, positional indices,
compatibility occurrences and required defaults, and adapts unsupported facts
only for the chosen destination. Information notices cover equivalent
normalization/reconstructable omissions; warnings cover meaningful loss or
uncertainty; errors reject invalid/unimplemented conversions. These decisions
never strip the authoring model to match the weakest destination.

Same-format round trips preserve meaning naturally through complete fields and
correct adapters. They do not promise every original byte: modernization,
bookkeeping and bounded text-layout calculations can differ. Stored identities,
connectivity and authored geometry remain strict. Conversions must not accumulate
incidental rounding shifts into authoring coordinates.

Private `_name` indexes and caches speed up queries and edits. They are not
public fields or additional authored facts and are not serialized. Optional
inspection metadata does not choose output eligibility or restore old values.

## Data editing boundary

The model maintains relationships while data is edited, including reference
indices and bound text. It does not provide geometric editing algorithms.
Changing component X/Y moves that component; existing wire points stay put.
Changing a library reference does not import a definition, replacing footprint
data does not reload another library, and editing a pour boundary does not
calculate its fill. Those operations require a higher-level toolkit above this
model. The [API guide](API.md) describes the supported edits and conversion
limits; the [schematic catalogue](SCHEMATIC.md) provides the field definitions.
