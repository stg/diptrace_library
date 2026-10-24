# The data model and editing API

Every normal import returns the same schematic `Document`. Its ordered tree
contains records, scalar/tuple fields and collections. Public ASC/DCHXML names
guide field names; serialized positions are adapter details.

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
order. The [generated catalogue](../references/MODEL_REFERENCE.md) lists the supported record
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

The model owns current design facts. Private `_name` lookup caches and reference
indexes are implementation details, do not appear as editable fields and are
not serialized. Imports modernize; detached exports adapt. The
[model contract](../references/MODEL_CONTRACT.txt) and
[capability register](../references/FORMAT_CAPABILITIES.txt) retain the detailed architectural
and format-specific rules.
