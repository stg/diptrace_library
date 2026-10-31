# The data model

The library separates shared model infrastructure from the meaning of each
document family. Documents, records, fields, ownership, queries and identity-based
relationships use the common model. A family defines its record types, units,
relationships and format adapters.

Schematics and PCB layouts use this infrastructure with their own records and
constraints. The first part of this guide describes the common model; the
[schematic](#schematic-documents) and [PCB](#pcb-documents) sections describe each
family's organization. Component and pattern libraries remain experimental.

- [Documents and records](#documents-and-records)
- [Field access](#field-access)
- [Schema and reflection](#schema-and-reflection)
- [Ownership and relationships](#ownership-and-relationships)
- [Editing and consistency](#editing-and-consistency)
- [Import and export](#import-and-export)
- [Schematic documents](#schematic-documents)
- [PCB documents](#pcb-documents)

## Documents and records

A `Document` owns an ordered tree of `Element` records and a relationship
graph. A record has a type, named fields and owned child records or collections.
The tree describes containment; the graph describes links between records.

```text
Document
  root                             outer container
    record
      field                        scalar, tuple or relationship value
      child record
      collection
        record
        record
```

This is a model outline, not a serialized file layout. The document family
determines the actual names and permitted contents. Public ASCII/XML vocabulary
guides those names where it is useful. File positions and redundant compatibility
values belong to adapters.

The document represents the current design. Meaningful values, persistent
identities, semantic ordering and unresolved references are model data.
Superseded values and original byte chunks are not retained merely to recreate
an input file.

Queries and child navigation return the actual records in the document.
Modifying a returned record edits the design; it does not edit a detached query
result. Query syntax and callable filters are described in the
[API reference](API.md#searching).

## Field access

Fields use Python mapping conventions:

| Operation | Rule |
| --- | --- |
| `record[name]` | Read a present field; missing names raise `KeyError`. |
| `record.get(name, default=None)` | Read a field, or return the default if absent. |
| `record[name] = value` | Validate and edit; equivalent to `record.set(name, value)`. |
| `name in record` | Test presence, independently of the value's truthiness. |
| `del record[name]` | Remove an optional stored field; missing fields raise `KeyError`. |
| `record.child(name)` | Navigate to an owned child record or collection; return `None` if missing. |

A field value can be a scalar, a tuple or a reference to another record.
A child collection is navigated with `child()` or a query, rather than read as
a scalar field. Tuple fields can also expose named members on their child record.

Presence, nullability and value are separate:

- An absent field has no value. `get()` returns its fallback.
- A present nullable field may hold `None`; that does not make it absent.
- Present zero, `False` and empty text remain those values, rather than using a fallback.

Unknown field writes raise `KeyError`. Invalid types, deletion of required
fields and writes to calculated fields are rejected before mutation.
Assigning `None` requires a nullable definition; use deletion to express absence.
A runtime relationship may impose further constraints on an otherwise writable
field.

Declared numeric fields require finite values. Integer fields reject fractional
numbers and booleans. Units and supported value domains belong to the family's
field definitions.

## Schema and reflection

A record's `schema` describes its declared fields and children. Definitions are
immutable and used by both editing validation and reflection.

| Definition | Describes |
| --- | --- |
| Record | Record type, named fields, permitted child records and collections |
| Field | Type, required presence, nullability, fallback, allowed choices, units, tuple members and calculated/read-only status |
| Child | Child name, allowed record types and minimum/maximum cardinality |

`record.schema.field(name)` retrieves a field definition.
`record.schema.children[name]` retrieves a child definition.
These describe what is allowed; field membership describes what is currently
present. A listed schema fallback is an adapter/construction fallback, not an
implicit value for `record.get()`.

Reflection does not introduce another editing mechanism. A field discovered by
name is read or written through the same bracket/get/set API as a known field.
See [fields and reflection](API.md#fields-and-reflection) for the definition
properties and validation methods.

## Ownership and relationships

A record has one owning parent. Collections preserve meaningful order.
Moving a record changes its parent or position while retaining its identity.
Cloning creates new in-memory identities.

There are three distinct ways to identify something:

| Identifier | Purpose |
| --- | --- |
| `uid` | Identify one in-memory record; stable through edits/moves, fresh in clones |
| Persistent key | Store a meaningful design identity defined by the document family |
| Position/index | Locate a record in a collection or serialized array; often derived from order |

Resolved relationships point to record identities. They do not rely on callers
keeping positional copies synchronized. A relationship can project a target's
index, key or property into the occurrences that require it. Reverse views and
bound text derive from their authoritative source; independently authored text
remains independent.

Unresolved relationships retain their supplied identity and scope explicitly.
They are not replaced with guessed targets. Their constraints can prevent an
edit that would silently reinterpret the unresolved identity.

The family defines which links have meaning and what scopes/constraints apply.
The common graph maintains those links. Its API is described under
[relationships](API.md#relationships).

## Editing and consistency

Supported named and structural edits maintain affected relationships
automatically. Invalid edits are checked before mutation. Ordinary edits and
saves do not require a manual rebuild.

- Changing a linked property updates its managed copies and calculated dependents.
- Reordering records keeps links attached to the same target identities.
- Copying remaps targets inside the copied subtree and retains external targets.
  Incoming users still refer to the original.
- Removing a subtree disposes of its owned links, but external users or unresolved
  scopes can block removal.

A single supported operation is checked as a unit. Several successive calls are
not a transaction with automatic rollback. Lower-level syntax/adapter operations
do not replace the named editing API.

`validate()` audits fields, ownership and relationships without changing design
facts. Advanced `rebuild()` additionally projects compatibility indices; it is
not a repair operation. Neither invents missing identities.

Private indexes and caches speed up lookup and incremental maintenance.
They are implementation state, not additional authored fields, and are not
serialized. See [construction and ownership](API.md#construction-and-ownership)
for operation-specific copy, move and removal rules.

## Import and export

All supported serializations of a family import into that family's same
editable model. Different document families need not have identical schemas.

**Import modernizes.** Supported older representations become current facts,
including established compatibility and geometry upgrades. Meaningful data is
not discarded merely because another destination cannot represent it. Import
consumes the supplied file without implicit companion discovery.

**Export adapts.** A writer prepares a detached view, generating bookkeeping,
positional indices, required defaults and redundant compatibility occurrences.
Destination limitations apply to that view; they do not strip the authoring
model to match the weakest format.

Unavailable optional/calculated data is absent, or explicitly `None` where
the schema permits it. There is no need for a second availability flag.
An authored choice and a missing calculated result can coexist. For example,
a PCB model can retain a requested filled pour without calculated fill
geometry; a writer that requires geometry for that state must adapt on export.

Information notices describe equivalent normalization or reconstructable
omissions. Warnings describe meaningful loss or uncertainty. Errors reject
invalid or unimplemented conversion. Reports and per-operation contexts stay
separate from design facts.

Same-format round trips preserve meaning through complete fields and correct
adapters. They do not promise every original byte: bookkeeping, modernization
and bounded text-layout calculations can differ. Conversions must not accumulate
incidental rounding shifts into authored coordinates. Optional inspection
metadata is not an export configuration or a backup of previous values.

## Schematic documents

This section describes the schematic family, rather than requirements of the
shared infrastructure above. DCH, ASC and DCHXML use one schematic model.

### Organization

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

Collection names are the names used in paths. Schema names identify record types:
symbol, sheet and footprint drawings have separate definitions even when their
child name is `Shape`. `//Part` can find cached definitions as well as placed
components; `/Schematic/Components/Part` restricts the search to placed records.

`schematic_schema()` returns the immutable schematic definitions without a
document. The [generated catalogue](SCHEMATIC.md) lists every declared record,
field, tuple member, type, unit and child cardinality.

### Connectivity and labels

For resolved electrical membership, a net's ordered `Parts/pt` members own
pin identities (`member["Pin"]`). `pin["Net"]` is the editable reverse view:
assign a net or `None` to connect, move or disconnect the pin. The member's
component/pin indices and the pin's `NetNumber` are calculated occurrences,
not independent assignments.

Wire attachments constrain membership changes. An operation that contradicts
an attached wire is rejected before mutation. Ambiguous, contradictory or
unresolved imports remain explicit and must be resolved before that relationship
can be changed. Copying a component does not copy a net's memberships.

Named component/property edits update affected bound labels and managed copies.
Bound label text is calculated: edit its source field, or choose literal text
(`FontType = 0`) before authoring independent text. Existing links and their
mode guards prevent changing a controller in a way that reinterprets the target.

`document.refdes(prefix)` provides a live view of enabled physical components
across sheets. RefDes identity is the exact prefix and trailing ASCII counter;
leading zeros do not matter, and a bare prefix means zero. Named edits check
collisions while retaining authored spelling. See the
[RefDes reference](API.md#reference-designators) for matching and allocation.

### Units and calculated fields

Schematic lengths use three shared units per millimetre. Adapters convert
physical units and XML's Y direction. Component placement angles use degrees;
text/label angles use radians. The model accepts angles outside a full turn.
Schematic output normalizes and rounds to quarter turns. Footprint and 3D angles
have separate domains and are not quantized as schematic placement.

An empty unit declaration means that the unit is unspecified.

Collection order supplies grid `Column`/`Row`, title-block `Position`,
pin/pad occurrence indices, and library slot/variant positions. Authored cell
bounds and persistent catalog keys remain independent data.
`PadTerminalCount` and terminal `Index` derive from the terminal list.
Page title blocks occupy six ordered slots.

The root owns `Scale` (percent), `Xpos` and `Ypos`; pages retain their own
saved views. Optional `Schematic.ActiveSheet` follows the selected page's
identity. XML output uses that selection unless an export context overrides it.
Simulator argument groups expose named fields and retain engineering expressions
as text. Compatibility vectors can declare an item type/fixed length without
inventing meanings for unknown members.

### Data editing and geometry

The model coordinates design references, not geometric editing algorithms.
Changing component X/Y moves the component; existing wire geometry stays where
it was. Changing a library reference does not import a definition. Replacing
footprint data does not reload another library, and editing a pour boundary does
not calculate fill geometry.

Routing, wire following and pour calculation require a higher-level toolkit
above the data model. They are not currently provided. The
[API reference](API.md) describes the available data operations and conversion
limits.

## PCB documents

DIP, PCB ASC and DIPXML import into one board model, with
`representation == "pcb"`. Its document class extends the same common tree and
reference graph as the schematic class; it adds PCB schemas and relationships.

| Collection | Meaning |
| --- | --- |
| `/Board/Components/Component` | Placed components and standalone physical objects |
| `Component/Pattern` | The instance's current pads, holes, drawings and dimensions |
| `/Board/Nets/Net` | Electrical membership and owned trace geometry |
| `/Board/Layers/Layer` | The copper layer stack |
| `/Board/ViaStyles/ViaStyle` | Via dimensions and copper spans |
| `/Board/CopperPours/CopperPour` | Boundaries, settings and any supplied calculated fill |
| `/Board/CacheLib` | Separate unplaced component and footprint definitions |

Use [PCB.md](PCB.md) for every record, field, type, unit and cardinality, and
[the PCB guide](PCB_GUIDE.md) for workflows and constructors.

A component owns its placed physical pattern. Its cached definition is a
separate editable object: changing a library path does not import or replace a
footprint. Pads relate to nets; nets own trace geometry. Endpoint references,
layer selections and other declared relationships use object identities, with
serialized selectors derived from current order. A static via's selected style
controls its copper size, drill and layer span.

Displayed RefDes labels do not establish schematic or hierarchy identity.
`HiddenId` and `HierarchyPath` carry that association. Imported duplicate labels
remain representable; renaming rejects newly introduced collisions. The shared
RefDes family helpers apply to both document families.

PCB lengths use three shared units per millimetre. Component placement angles
use radians and permit continuous rotation. Other angle domains remain explicit
in their field definitions; schematic quarter-turn rules do not apply to them.

These data operations do not route traces, follow moved components, recalculate
pour fill or rerun design checks. Supplied results remain explicit data; missing
calculated geometry remains absent. Export adapts unavailable results to its
destination without changing the design being edited.
