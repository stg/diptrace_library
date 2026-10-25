# API reference

The public entry point is `lib`. This page describes call signatures, arguments,
results and failure behavior. For a first workflow, use
[Getting started](GETTING_STARTED.md); for ownership and design meaning, use
[The data model](MODEL.md). Schematic record and field definitions are in
[SCHEMATIC.md](SCHEMATIC.md).

`Document`, `Element` and the relationship/schema infrastructure provide the
shared editing API. The published readers, writers, constructors and contexts
currently support schematic documents.

| Area | Entries |
| --- | --- |
| [Input and output](#reading-and-writing) | `read`, `parse`, `write`, `serialize`, document output methods |
| [Documents](#document) | State, identity lookup, validation and cloning |
| [Records](#fields-and-reflection) | Named field access, child navigation, schema reflection |
| [Queries](#searching) | `select`, `one`, `find_all`, selectors and `where` |
| [Reference designators](#reference-designators) | Family matching, numbering and allocation |
| [Construction and ownership](#construction-and-ownership) | Constructors, attachment, copying, movement and removal |
| [Relationships](#relationships) | Pin/net assignment, graph inspection and retargeting |
| [Configuration](#configuration) | Import/export contexts, layout services and path variables |
| [Reports](#reports) | Notices, severities, collection and reset |
| [Versions](#versions) | Capability queries and output-version selection |
| [Geometry](#geometry) | Bounds, arc/ellipse helpers and route-point cleanup |
| [Source inspection](#source-inspection) | Syntax views and lower-level operations |
| [Extensions and failures](#extensions-and-failures) | Adapter registration and exceptions |
| [Conversion limits](#conversion-limits) | Current format/version consequences |

**Example conventions.** Examples are independent, not a script to run from top
to bottom. Unless an example creates its own input, `design` is a loaded
schematic, `part` is a placed component, `pin` is one of its pins and `net`
is a net in that document. Filenames are illustrative. Arguments after `*`
are keyword-only.

## Reading and writing

### `read()`

```text
read(path, *, format=None, family=None, context=None, report=None, label=None, **options)
    -> Document
```

Read one file into the family's editable model. For DCH, ASC and DCHXML,
the result has `representation == "schematic"`.

| Argument | Meaning |
| --- | --- |
| `path` | Input filename as `str` or `pathlib.Path` |
| `format` | Format name; `None` infers it from the extension |
| `family` | Optional document family; see [family selection](#document-families) |
| `context` | Optional [ImportContext](#importcontext) |
| `report`, `label` | Optional [diagnostic collection](#reports) and caller label |
| `**options` | [Format-specific input options](#format-options) |

**Returns:** a `Document`. Only the supplied file is read; library references
and companion filenames are not opened implicitly.

**Raises:** file I/O/decoding exceptions, `ValueError` for an unsupported
format/version or invalid semantic mapping, and `TypeError` for invalid options.

```python
from lib import read

design = read("design.dch")
```

### `parse()`

```text
parse(data, *, format, family=None, context=None, report=None, label=None, **options)
    -> Document
```

Import an in-memory buffer with the same model and options as `read()`.

- `data`: bytes for any supported format; ASC and DCHXML also accept `str`.
- `format`: required, because there is no filename to infer it from.
- Other arguments: as for `read()`.

**Returns:** a `Document`. Failures follow `read()`, excluding file I/O.

```python
from pathlib import Path
from lib import parse

design = parse(Path("design.dchxml").read_bytes(), format="dchxml")
```

### `write()`

```text
write(document, path, *, format=None, family=None, context=None, report=None, label=None, **options)
    -> None
```

Write the current design to a file. Export prepares a detached view; it does not
change authored values to fit the destination.

| Argument | Meaning |
| --- | --- |
| `document` | Document to export |
| `path` | Output filename as `str` or `pathlib.Path` |
| `format` | Output format; `None` infers it from the extension |
| `family` | Optional document family; see [family selection](#document-families) |
| `context` | Optional [ExportContext](#exportcontext) or destination subclass |
| `report`, `label` | Optional [diagnostic collection](#reports) and caller label |
| `**options` | `version` and [format-specific output options](#format-options) |

**Returns:** `None`.

**File behavior:** overwrites the supplied path; its parent directory must exist.
The library does not perform an atomic filesystem replacement.

**Raises:** file I/O/encoding exceptions, `ValueError` for unsupported output
choices, `IncompleteDocumentError` for partial input, or a model/reference
validation exception. A report does not suppress these failures.

```python
from lib import write

write(design, "converted.dchxml")
```

### `serialize()`

```text
serialize(document, *, format, family=None, context=None, report=None, label=None, **options)
    -> bytes
```

Export to a byte buffer, using the same adapters and options as `write()`.
`format` is required. The result is always `bytes`, including for ASC/XML.

```python
from lib import serialize

data = serialize(design, format="dchxml")
xml_text = data.decode("utf-8")
```

### Document families

`family` accepts `"schematic"`, `"pcb"`, `"component"` or `"pattern"`, ignoring
case. When omitted, input uses the binary signature, ASC `Source` declaration
or XML root/type declaration to identify the family. Output uses the document's
current representation or source-tree declaration. An explicit family overrides
this detection. There is no preferred family for ASC. Headerless syntax fragments
require an explicit family for source inspection.

Only schematic adapters are currently available. An unavailable family, unknown
format or unrecognized input raises `UnsupportedFileError`, a `ValueError`
subclass; import/export reports collect the failure as usual. Known unsupported
versions use this same exception family. Ordinary parsing errors and file access
failures retain their existing exception types.

`lib.pcb`, `lib.component` and `lib.pattern` are placeholders exposing `read`,
`parse`, `write`, `serialize` and `format_capabilities` with their family selected.
They currently provide no conversion support, models or contexts.

`document_family(document) -> str` returns the current family using the same
model/declaration rules as export. It does not use provenance metadata. An
unidentifiable document raises `UnsupportedFileError`.

### Format options

Format names are case insensitive and accept a leading dot.
`"DCH"`, `"dch"` and `".dch"` select the same adapter.

All outputs accept `version`, using the adapter's default if omitted.
Input versions are detected from the file. Output does **not** automatically
reuse the input version. See [Versions](#versions) for selection and
[the support table](../README.md#schematics) for current ranges.

| Input | Option | Default and behavior |
| --- | --- | --- |
| DCH | `ansi_encoding` | `"cp1252"`; decoding for pre-Unicode strings |
| DCH | `allow_partial` | `False`; opt in to incomplete inspection data |
| DCH | `component_limit` | `None`; optional limit for inspection |
| ASC | `encoding` | `None`; UTF-8 with BOM, otherwise Windows-1252 |
| DCHXML | — | XML declaration controls byte decoding |

| Output | Option | Default and behavior |
| --- | --- | --- |
| ASC | `encoding` | Context encoding, otherwise Windows-1252 |
| ASC | `preserve` | `True`; syntax preservation on an explicit source view |
| ASC | `allow_partial` | `False`; partial syntax output is an inspection escape hatch |
| DCHXML | `newline` | `"\n"`; `"\r\n"` is also accepted; byte output is UTF-8 |

Partial/limited imports are not complete editable designs. Normal writers reject
incomplete documents. Source-view preservation is separate from meaningful
round trips through the shared model.

### Document output methods

These use the same options and diagnostic contract as `write()`/`serialize()`.
The `version` default is the relevant adapter's default.

| Method | Result | Accepted keyword options |
| --- | --- | --- |
| `to_dch_bytes()` | `bytes` | `version`, `context`, `report`, `label` |
| `to_asc()` | `str` | `version`, `context`, `report`, `label`, `preserve=True`, `allow_partial=False` |
| `to_asc_bytes()` | `bytes` | Same as `to_asc()`, plus `encoding=None` |
| `to_dchxml()` | `str` | `version`, `context`, `report`, `label`, `newline="\n"` |
| `to_dchxml_bytes()` | UTF-8 `bytes` | Same as `to_dchxml()` |
| `save_dch(path, ...)` | `None` | Same as `to_dch_bytes()` |
| `save_asc(path, ...)` | `None` | Same as `to_asc_bytes()` |
| `save_dchxml(path, ...)` | `None` | Same as `to_dchxml_bytes()` |

## Document

Normally obtain a document from `read()`, `parse()` or `new_schematic()`.
The low-level constructor is `Document(root=None, *, representation="tree")`;
it does not populate schematic records or defaults.

### State

| Attribute | Meaning |
| --- | --- |
| `root` | Outer owning `Element` |
| `representation` | Current API view; `"schematic"` for normal schematic imports |
| `references` | Identity-based `References` graph |
| `complete` | Whether the import is complete |
| `diagnostics` | Retained diagnostic strings |
| `metadata` | Optional inspection/provenance data, not export configuration |

### Methods

| Signature | Returns | Behavior |
| --- | --- | --- |
| `get(uid)` | `Element` | Look up an in-memory identity; unknown UID raises `LookupError` |
| `validate()` | `None` | Audit fields, ownership and relationships without changing design facts |
| `clone()` | `Document` | Independent tree and graph with fresh record UIDs |
| `unresolved()` | `list[str]` | Document diagnostics and incomplete-record annotations; graph issues are separately in `references.issues` |
| `rebuild(*, force=True)` | UID-to-element `dict` | Advanced audit plus projection of compatibility indices |
| `rebuild_index()` | UID-to-element `dict` | Build only the identity lookup dictionary |

Queries are described under [Searching](#searching); copying/removal under
[Construction and ownership](#construction-and-ownership).

Ordinary edits and saves require no rebuild. Validation may accept intact
unresolved identities; it does not guess targets. Neither validation nor
rebuilding performs geometric repair.

## Fields and reflection

### Named field access

These operations apply to schema-bound `Element` records.

| Operation | Result / behavior |
| --- | --- |
| `record[name]` | Present value; `KeyError` if missing or unknown |
| `record.get(name, default=None)` | Present value, or default only when absent |
| `record[name] = value` | Validated assignment |
| `record.set(name, value)` | Same assignment; returns `None` |
| `name in record` | Presence test; zero, false, empty text and `None` remain present |
| `del record[name]` | Remove an optional field |

**Constraints:** unknown writes raise `KeyError`. Read-only assignment,
required-field deletion and child-container scalar access raise `TypeError`.
Invalid values or relationship changes fail before mutation.

`get()` does not replace a present `None` or empty string with its default.
Assigning `None` requires a nullable field and differs from deleting it.
Integer fields reject booleans/fractional values; numbers must be finite.

```python
part["Value"] = "22k"
datasheet = part.get("Datasheet", "")
if "Datasheet" in part:
    del part["Datasheet"]
```

Tuple fields read/write as tuples. Named tuple members can also be accessed
through their child record, for example `part.child("ShowRefDes")["Align"]`.

### Record navigation and identity

| Signature/property | Result |
| --- | --- |
| `child(kind)` / `find(kind)` | First matching child, or `None` |
| `children(kind=None)` | New list of direct child records; optionally filter by name |
| `walk(*, include_self=False)` | Depth-first iterator |
| `descendants(kind=None)` | List of descendants; optionally filter by name |
| `uid` | Stable in-memory identity through edits/moves; fresh in clones |
| `kind` / `type` | Record's child/type name; `type` is an alias |
| `parent` | Owning parent, or `None` |
| `path` | Current ordinal path; changes when ordering changes |
| `changed` | Whether the record or descendants changed since loading |
| `schema` | Immutable record definition, or `None` for untyped syntax |

`children()` returns a new list of the actual records, not cloned records.
`changed` is not a persistent revision or file hash.

### Schema definitions

`schematic_schema()` returns the immutable mapping of schematic record names
to definitions. `record.schema` returns the definition for one record.
The same definitions drive validation, reflection and the
[generated schematic catalogue](SCHEMATIC.md).

| Definition | Attributes |
| --- | --- |
| `Record` | `name`, `description`, `fields`, `children` |
| `Field` | `name`, `kind`, `required`, `nullable`, `default`, `choices`, `unit`, `description`, `readonly`, `members`, `item_kind`, `length` |
| `Child` | `name`, `record` (allowed record types), `minimum`, `maximum`, `description` |
| `MISSING` | Sentinel indicating no schema fallback |

The definition types and `MISSING` are available from `lib.common.schema`.
A schema fallback is an adapter/construction fallback, not an implicit read value.
`maximum=None` means an unbounded child count.
An empty `choices` tuple leaves the field's values unrestricted within its type;
a populated tuple lists the accepted values.

| Method | Behavior |
| --- | --- |
| `Record.field(name)` | Return a `Field`; unknown name raises `KeyError` |
| `Field.validate(value)` | Validate type/value; reject read-only assignment |
| `Record.validate_fields(record)` | Audit stored/required fields |
| `Record.validate_children(record)` | Audit child types and cardinality |

Application edits use the ordinary named API, including when names come from
reflection. Definition parameter mappings, callbacks and dependency declarations
are adapter infrastructure.

```python
for name, definition in part.schema.fields.items():
    if name in part:
        print(name, definition.kind, part[name])
```

## Searching

### `select()` and `one()`

```text
document.select(path, *, where=None) -> list[Element]
element.select(path, *, where=None)  -> list[Element]
document.one(path, *, where=None)   -> Element
element.one(path, *, where=None)    -> Element
```

| Argument | Meaning |
| --- | --- |
| `path` | Nonempty selector string; absolute or relative |
| `where` | Optional callable receiving each final match |

**Results:** `select()` returns matches in tree order. `one()` requires exactly
one match after filtering and raises `LookupError` otherwise.

**Raises:** `ValueError` for unsupported selector syntax, `TypeError` for a
non-callable `where`. Exceptions inside the predicate propagate.

### Selector syntax

| Form | Meaning |
| --- | --- |
| `/Schematic/Components/Part` | Absolute path from the document root |
| `Pins/Pin` | Relative child path |
| `//Part` | Descendants named Part, including cached definitions |
| `*` | Any child name |
| `Part[2]` | Second matching child of each selected parent; one-based |
| `Part[RefDes="R1"]` | Exact text equality |
| `Part[Enabled=true]` | Boolean equality (`false` is also accepted) |
| `Part[Page=0]` | Numeric equality |
| `/` | Outer document root |

Each step accepts one ordinal or equality predicate. Text can use either quote
style; double a matching quote inside a literal, as in
`Part[Name='Jack''s connector']`. `//Part` includes definitions; use
`/Schematic/Components/Part` for placed components.

The syntax is not XPath: it has no parent axes, ranges, regular expressions or
boolean expressions. Exact text predicates distinguish `R003` from `R3`;
numeric RefDes matching is provided by [family helpers](#reference-designators).

### Field filtering with `where`

Use Python comparisons for conditions beyond selector equality. The predicate
runs only on final matches and preserves their order.

```python
parts = design.select(
    "/Schematic/Components/Part",
    where=lambda p: p["Enabled"] and p["Value"] == "10k",
)
in_area = design.select(
    "/Schematic/Components/Part",
    where=lambda p: p["Page"] == 0 and 0 <= p["X"] <= 30 and 0 <= p["Y"] <= 30,
)
```

The second query tests stored origins in shared units, not visible bounds or
symbol intersection. There is no geometric selection operation.

### `find_all()`

```text
document.find_all(kind, *, where=None) -> list[Element]
element.find_all(kind=None, *, recursive=False, where=None) -> list[Element]
```

Document search is recursive. Element search defaults to direct children;
`recursive=True` includes descendants. On an element, `kind=None` accepts
all child names. `where` has the same filtering behavior as `select()`.

## Reference designators

### `Document.refdes()`

```text
document.refdes(prefix) -> RefDesFamily
```

Return a live numbered-family view of enabled physical components across all
sheets. Logical symbols, disabled components and cached definitions do not occupy
names in this view. `matches()` returns component records; numbering methods
return strings. No operation reserves or assigns a name.

### `RefDesFamily` and `split_refdes()`

```text
RefDesFamily(prefix, references, *, get_refdes=None)
split_refdes(reference) -> tuple[str, int]
```

| Argument | Meaning |
| --- | --- |
| `prefix` | Exact case-sensitive family prefix; cannot end in an ASCII digit |
| `references` | Iterable of names/items, or zero-argument callable supplying current items |
| `get_refdes` | Optional `get_refdes(item) -> str` for record-like items |
| `reference` | Nonempty name for splitting or lookup |

An ordinary iterable is captured once; a callable makes the source live.
`split_refdes()` returns the exact prefix and final ASCII numeric counter:

| Name | Prefix | Counter |
| --- | --- | --- |
| `R003` | `R` | 3 |
| `R`, `R0`, `R000` | `R` | 0 |
| `R-1` | `R-` | 1 |
| `R1-X12` | `R1-X` | 12 |
| `R1-12` | `R1-` | 12 |

Punctuation stays literal; counters are never negative. Non-ASCII digits remain
prefix characters. Ordinary spaces are rejected. Empty stored names are
unassigned and skipped by a family; `split_refdes("")` raises `ValueError`.

### Family methods

| Signature | Returns / behavior |
| --- | --- |
| `matches(reference=None)` | All items in the family, or all items with the supplied numeric identity; includes multipart units |
| `designators()` | Distinct authored spellings in numeric order |
| `reference in family` | Numeric-identity membership; an invalid lookup name returns false |
| `first()` / `last()` | Lowest/highest occupied spelling, or `None` |
| `first_free(start=1)` | First available counter at/above `start`; nonnegative integer required |
| `next(reference, *, mode)` | Strictly following number/name |
| `previous(reference, *, mode)` | Strictly preceding number/name, stopping at zero |

`matches()` orders items by counter, spelling, then source order.
Existing-name results retain authored spelling; generated names are unpadded.
For `next()`/`previous()`, `mode` is required:

| Mode | Search |
| --- | --- |
| `"number"` | Step by one, whether occupied or free |
| `"existing"` | Find the next/previous occupied counter; `None` without a match |
| `"free"` | Skip occupied counters; `previous()` returns `None` if no free predecessor exists |

**Raises:** `ValueError` for invalid modes, counters, prefixes or names;
`TypeError` for incompatible argument types. Queries that inspect malformed
stored names raise rather than treating a possibly occupied number as free.

```python
refs = design.refdes("R")
available = refs.first_free()
units = refs.matches("R003")
previous = refs.previous("R10", mode="existing")
following = refs.next("R10", mode="free")
```

For a standalone list:

```python
from lib import RefDesFamily

refs = RefDesFamily("R1-X", ["R1-X1", "R1-X003"])
available = refs.first_free()                    # R1-X2
previous = refs.previous("R1-X4", mode="existing")  # R1-X003
```

### Editing rules

`R003` and `R3` occupy the same numbered name. So do a bare prefix and its zero
suffix. Renaming rejects another component's occupied name before mutation,
across sheets and hierarchy. A spelling-only change is valid when unshared.
Imported duplicates retain their separate identities and remain editable;
assigning an unchanged name is allowed, but renaming away does not reserve it
for later reuse. Units of one multipart component may share a name. These
helpers do not coordinate renaming a whole group; existing managed property-copy
relationships follow valid edits.

Imports do not silently remove spaces from source names. The stricter helper
and named-authoring rules do not rewrite a file's imported data.

## Construction and ownership

### Schematic constructors

| Signature | Returns |
| --- | --- |
| `new_schematic(sheet_name="Sheet 1")` | `Document` with a page, settings and empty collections |
| `new_symbol(name="", reference="", *, placed=True)` | Detached placed component, or cached definition when false |
| `new_pin(index=0, *, placed=True)` | Detached pin or cached pin |
| `new_net(name="")` | Detached net with empty member/wire collections |
| `new_wire(*, bus=False)` | Detached wire/bus line with empty points and unassigned endpoints |
| `new_schematic_shape(index=0)` | Detached sheet drawing with editable points/text |

Attached occurrence indices follow collection order. Constructors supply
authoring defaults, not routed geometry or imported external definitions.

```python
from lib import new_schematic, new_symbol

design = new_schematic(sheet_name="Example")
part = design.one("/Schematic/Components").append(new_symbol("Resistor", "R1"))
part["Value"] = "10k"
```

### Attach, move and detach

| Signature | Result / behavior |
| --- | --- |
| `parent.append(node)` | Attach a detached node at the end; return it |
| `parent.insert(node, index=None)` | Attach at zero-based child position; `None` appends; return it |
| `parent.add(kind, *values)` | Construct/attach an `Element`; return it |
| `node.move_to(parent, index=None)` | Move/reorder the same record with its links; return it |
| `node.detach()` | Detach conservatively; dependencies may block it; return it |
| `parent.remove(node)` | Require the node to be this parent's child, then detach; return it |

A record cannot have two parents. Structural edits preflight keys, cardinality
and relationship scopes. Protected attachment segments cannot be split.
For complete domain objects, prefer constructors to a bare `add()`.

### Copy and remove

```text
document.copy(node, *, parent=None, index=None, fields=None) -> Element
document.remove(node) -> Element
element.clone() -> Element
document.clone() -> Document
```

| Operation | Ownership / relationships |
| --- | --- |
| `document.copy()` | Copy attached non-root content and its owned links; remap internal targets, keep external targets |
| `document.remove()` | Detach non-root content and discard its owned links; external users/scopes may block removal |
| `element.clone()` | Detached tree copy with fresh UIDs, without arbitrary graph links |
| `document.clone()` | Independent full design and graph with fresh record UIDs |

For `copy()`, `parent=None` uses the original parent and `index=None` appends.
`fields` is an optional mapping of root field overrides, applied before
attachment and checked with copied relationships.

Incoming users stay on the original. For example, copying a component does not
also copy a net's memberships. Several calls remain separate edits, not a
transaction with automatic rollback.

```python
duplicate = design.copy(
    part,
    fields={"RefDes": design.refdes("R").first_free()},
)
duplicate.move_to(duplicate.parent, index=0)
design.remove(duplicate)
```

## Relationships

### Pin/net assignment

`pin["Net"]` reads the pin's current net, or `None` when unconnected.
Assign a net from the same document or `None` to move/disconnect it.
The corresponding ordered net membership and numeric occurrences update
automatically. A wire contradiction or unresolved constraint can block the edit.

```python
pin["Net"] = net
pin["Net"] = None
```

This changes connectivity data, not attached wire geometry. Other relationship
fields are identified in the [schematic catalogue](SCHEMATIC.md).

### `References`

Use `document.references` rather than constructing a graph separately.
Iteration yields immutable `Reference` objects; `len(graph)` counts resolved
links.

| Signature / property | Result / behavior |
| --- | --- |
| `get(uid)` | Current `Reference`; unknown UID raises `LookupError` |
| `incoming(target, *, role=None)` | List of links to the target |
| `outgoing(source, *, role=None)` | List of links from the source |
| `retarget(reference, target)` | Validate/change target; return replacement `Reference` with the same UID |
| `discard(reference)` | Remove a binding subject to domain constraints |
| `issues` | Unresolved-reference records with retained identities/scopes |
| `validate()` | Audit links without inventing missing targets |

`role=None` accepts all roles; a string filters by relationship role.
After retargeting, use the returned reference or `get(uid)`. Discarding a binding
does not make retained literal projection values a new resolved relationship.

```python
links = design.references.incoming(pin, role="net-member")
for link in links:
    print(link.role, link.source.path)
```

### Reference records

| Type | Fields |
| --- | --- |
| `Reference` | `uid`, `source`, `target`, `role`, `indices`, `guards` |
| `UnresolvedReference` | `source`, `message`, `indices`, `collections`, `guards` |
| `Segment(start, end)` | Adjacent route-point pair used as a reference target |

A resolved target is an element or a `Segment`. Unresolved scope protects
retained data against edits that would silently reinterpret its identity.
Named property edits also maintain bound labels/copies; independently authored
text stays independent.

### Advanced graph binding

```text
graph.bind(source, target, *indices, role="", guards=(), preserve=False) -> Reference
graph.note(source, message, *indices, collections=None, guards=()) -> UnresolvedReference
graph.discard_issue(issue) -> None
graph.manages(field, argument=0) -> bool
graph.unresolved_slot(field, argument=0) -> bool
```

These are adapter/custom-model operations. `bind()` creates an identity link
and projects its target data. `preserve=True` instead requires the existing
values to agree. `note()` registers unresolved data and its protected scope;
`discard_issue()` explicitly removes it. Do not mutate `issues` directly.

| Projection / guard | Meaning |
| --- | --- |
| `Index(field, argument=0, ancestor=0, offset=0)` | Target collection position, optionally from an ancestor |
| `Key(field, name="Id", argument=0, ancestor=0)` | Unique named target key |
| `Property(field, name=None, argument=0, ancestor=0, target_argument=0)` | Target property/tuple member, without a uniqueness requirement |
| `Guard(field, values)` | Controlling field must keep an allowed value |
| `OrdinalGuard(field, member)` | Member must remain inside an inclusive active-prefix limit |

`field` is the field's child element. `argument` is a zero-based slot.
`ancestor` climbs from the target before projection; `Property.name=None`
selects the target's own arguments. Custom bindings do not extend an adapter's
file vocabulary. Invalid bindings/retargets raise `ReferenceError` or another
validation exception before mutation.

## Configuration

Contexts are immutable dataclasses. They hold operation choices, not design
facts. Construct one with keyword arguments; use `dataclasses.replace()` for
a modified copy. Ordinary input/output does not require a context.

For export, precedence is **explicit override → stored setting → standard
default**. Standard display/text choices are mm, vector text and font size 2.
The contexts below currently belong to the schematic adapters.

### `ImportContext`

```text
ImportContext(font_size=2, font_name="", text_layout=None)
```

Supply environment choices needed to modernize older DCH input.

| Field | Meaning |
| --- | --- |
| `font_size` | Positive integer fallback for missing old font settings |
| `font_name` | Environment font family for legacy placement; does not replace a stored drawing family |
| `text_layout` | Optional `TextLayout` service |
| `layout` (property) | Supplied layout service, or the default service |

Stored settings take precedence. Other normal input formats accept the common
`context` argument but do not currently need these DCH modernization choices.

### `ExportContext`

| Field | Default | Meaning |
| --- | --- | --- |
| `units` | `None` | Stored display units, then mm; override with `"mm"`, `"mil"`, `"in"`/`"inch"` |
| `project_dir` | `None` | Stored ProjectDir, then empty text; no directory lookup |
| `marking_style` | `None` | Stored/default marking choices, or explicit `MarkingStyle` |
| `grid_snap` | `None` | Stored choice, then true; an explicit DCH override is rejected |
| `text_layout` | Default service | Vector/system text measurement service |
| `use_part_font_color` | `None` | Stored choice, then false |
| `additional_user_fields` | `()` | Extra global rows `(display_name, key, state, position)` |
| `legacy_picture_files` | `None` | Filename tuple indexed by an unresolved old BitmapIndex; files are not opened |
| `path_variables` | `None` | Explicit `PathVariables` configuration |
| `refresh_user_fields` | `False` | Refresh global user-field choices on the detached output view |

An override changes only the output. Display units do not change shared
in-memory length units.

```python
from lib import ExportContext, write

write(design, "in_mils.dchxml", context=ExportContext(units="mil"))
```

### Destination contexts

All inherit the common export fields. Unsupported explicit choices raise
rather than being silently ignored.

| Context | Additional field | Default / behavior |
| --- | --- | --- |
| `DchExportContext` | `compact_inactive` | `None` resolves to false |
| `DchExportContext` | `default_main_supplier` | `False`; fallback for a missing old supplier-match flag |
| `AscExportContext` | `compact_inactive` | `None` resolves to true |
| `AscExportContext` | `default_main_supplier` | Same fallback as DCH |
| `AscExportContext` | `encoding` | `None` resolves to Windows-1252 |
| `AscExportContext` | `line_width` | Optional `line_width(layer)` callback; default returns 0.1 shared length unit |
| `AscExportContext` | `legacy_text_slots` | `None`, or six values: two modes, two alignments, two field names |
| `DchXmlExportContext` | `active_sheet` | `None` follows stored selection, then page zero; explicit index must be nonnegative |

Compaction cannot discard referenced content. Reports identify omitted inactive
records and other consequences.

### `resolved()`

```text
ExportContext.resolved(document, *, format=None) -> ExportContext
DchExportContext.resolved(document) -> DchExportContext
AscExportContext.resolved(document) -> AscExportContext
DchXmlExportContext.resolved(document) -> DchXmlExportContext
```

Return an independent context with effective stored/default choices filled in.
On a common context, `format` selects the destination class and policy.

Resolve for the actual destination. Transferring an already resolved context
can include a choice another format cannot represent, such as DCH `grid_snap`.

```python
from dataclasses import replace
from lib import ExportContext, write

defaults = ExportContext().resolved(design, format="dchxml")
custom = replace(defaults, units="mil")
write(design, "custom.dchxml", context=custom)
```

### Font and layout services

These supplementary types are imported from their owning modules.

| Type / import | Constructor fields |
| --- | --- |
| `lib.common.text.markings.MarkingStyle` | `font_size=2`, `font_name=""`, `vector=True`, `font_width=-2.0`, `font_scale=1.0`, `font_color=0`, `pen_width=1.0`, `mono=False` |
| `lib.common.text.layout.TextLayout` | `measure_system=None`, `resolution=10.0`, `font_scale=1.0` |
| `lib.common.text.windows.WindowsFontMetrics` | `dpi=96` (keyword-only) |

The previous schematic import paths remain available for these same types.
`TextLayout.symbol_bounds(shape)` returns two text-box corners for symbol text;
`pattern_bounds(shape)` does the same for footprint text. Both include all text
lines and the full authored angle, leaving stored geometry unchanged.
A system-font callback has signature `(text, family, point_size)` and returns
an object with pixel `width`/`height`. `WindowsFontMetrics.measure`
provides that interface on Windows; other platforms can supply a service.
Resolution/scale must be finite and positive.

Vector layout is self-contained. The default service loads Windows measurement
lazily only when system text needs it. If required measurement is unavailable,
conversion raises `NotImplementedError` instead of inventing text bounds.

### `PathVariables`

| Field | Default | Meaning |
| --- | --- | --- |
| `main_dir`, `program_docs`, `my_docs` | `""` | Explicit directory values |
| `standardlibs`, `maindir`, `programdocs`, `mydocs` | `True` | Enable corresponding variable spellings |
| `custom` | `()` | Rows `(name, value, enabled)` |

```text
PathVariables.select(variable, actual, *, project_dir="", include_project=True)
    -> str
```

Choose an output path spelling from the variable and actual filename forms.
Configuration is explicit: it reads neither environment variables nor the
registry/filesystem. Cyclic or excessive expansion raises `ValueError`.
Invalid directory/row types raise `TypeError`.

## Reports

### `ConversionReport`

```text
ConversionReport()
```

Collect ordered diagnostics across imports and exports. `ImportReport` and
`ExportReport` are aliases of the same class.

The optional `notices` constructor argument accepts an initial list of notices.
When omitted, each report starts with its own empty list.

| Member | Result / behavior |
| --- | --- |
| `notices` | List of all `ConversionNotice` objects in collection order |
| `infos` | New list filtered to information notices |
| `warnings` | New list filtered to warnings |
| `errors` | New list filtered to errors |
| `clear()` | Empty the collector in place; return `None` |

Reusing a report appends notices. Recreate it for an independent collection,
or clear it for another job. Previously retrieved filtered lists are snapshots.
A report records diagnostics, not entries for every clean success.

```python
from lib import ConversionReport, read, write

report = ConversionReport()
design = read("design.dch", report=report)
write(design, "reported.dchxml", report=report)
for notice in report.notices:
    print(notice.severity, notice.operation, notice.rule, notice.message)
report.clear()
```

### Severity and failure behavior

| Severity | Meaning | Without a supplied report |
| --- | --- | --- |
| `info` | Equivalent normalization or reconstructable output | Quiet |
| `warning` | Meaningful loss, unresolved data or deferred normalization | Python `ConversionWarning` |
| `error` | Invalid or unimplemented operation | Original exception is raised |

With a report, notices are collected instead of emitting automatic warnings.
An error is recorded before raising; collection does not allow invalid work to
continue. Argument/report-type errors remain ordinary argument errors.

`report` and `label` are optional on the unified input/output functions and
document conversion methods. Labels must be strings. File operations record the
supplied path; buffer operations have no filename and can use a label.

### `ConversionNotice` and `ConversionWarning`

A notice is immutable.

| Field | Meaning |
| --- | --- |
| `rule` | Machine-readable rule name |
| `message` | Human-readable explanation |
| `severity` | `"info"`, `"warning"` or `"error"` |
| `operation` | `"import"` or `"export"` |
| `format` / `destination` | Input/output format; `format` is the operation-neutral alias |
| `paths` | Tuple of affected record paths |
| `recoverability` | Description of what remains/reconstructs |
| `file` | Supplied filename, or `None` |
| `label` | Caller label, or `None` |

The constructor is `ConversionNotice(rule, destination, message, paths=(),
recoverability="not preserved in destination", severity="warning",
operation="export", file=None, label=None)`.

`ConversionWarning(notice)` is a `UserWarning` subclass with a `notice`
attribute. Python's `warnings` module can filter or log these warnings.

## Versions

### `format_capabilities()`

```text
format_capabilities(format, *, family=None) -> FormatCapabilities
```

Return the immutable capability declaration for an adapter. Format names accept
case differences and a leading dot. Unique native/XML names identify their
family. ASC has several dialects and requires an explicit `family`; omitting it
raises `ValueError`. Unknown names and unavailable families raise
`UnsupportedFileError`.

| Attribute | Meaning |
| --- | --- |
| `format` | Canonical format name |
| `family` | Owning document family |
| `read_versions` | Tuple of recognized input revisions |
| `write_versions` | Tuple of selectable output revisions |
| `default_write_version` | Output revision used when omitted |

DCH revisions are schema integers. DCHXML input revisions are vocabulary strings
such as `"5.3"`; its output revisions are target schematic schema integers.
These numbers are not application release numbers. Current ranges and known
release mappings are listed in [the support table](../README.md#schematics).

### `FormatCapabilities` methods

| Signature | Result |
| --- | --- |
| `supports_read(version)` | Whether an exact input revision is supported |
| `supports_write(version)` | Whether an exact output revision is supported |
| `output_version(requested=None, *, fallback=False)` | Supported output revision, or `ValueError` |

`output_version()` returns the default when `requested` is `None`.
Otherwise it requires exact support. With explicit `fallback=True`, an
unsupported integer request may select the highest supported earlier revision.
It never upgrades; it still raises if no earlier revision is supported.
A caller permitting fallback should report a changed choice.

```python
from lib import format_capabilities, write

capabilities = format_capabilities("dch")
target = capabilities.output_version(52)
write(design, "target.dch", version=target)
```

Capability queries describe adapter support, not design-specific losses.
Review conversion notices when targeting another format/version.

## Geometry

These helpers calculate local bounds or manipulate existing point data.
They do not route connections or implement geometric selection.

| Signature | Result / constraints |
| --- | --- |
| `Bounds(left, top, right, bottom)` | Immutable bounding rectangle |
| `Bounds.from_points(points)` | `Bounds` or `None` for no points; nonfinite coordinates raise `ValueError` |
| `bounds.width`, `bounds.height`, `bounds.center` | Dimensions and centre pair |
| `bounds.union(other)` | New bounds covering both rectangles |
| `circular_arc_bounds(start, middle, end)` | Bounds including cardinal extrema on the arc |
| `ellipse_points(first, opposite, *, segments=30, closed=False)` | Tuple of samples from opposite bounding corners; at least three segments |
| `symbol_bounds(part)` | Local enabled-pin/non-text-drawing bounds |
| `pattern_bounds(pattern)` | Local pad/hole/non-text-drawing bounds |

`symbol_bounds()` excludes placement, rotation, pen width and labels.
`pattern_bounds()` raises `NotImplementedError` for unsupported contours or
rotations. `ellipse_points(closed=True)` repeats the first point.
For collinear arc points, `circular_arc_bounds()` returns point bounds;
equal start/end points denote a circle whose middle point is opposite.

### `coalesce_routes()`

```text
coalesce_routes(document, *, enabled_only=False) -> tuple[RemovedRoutePoint, ...]
```

Remove excess coincident wire points while retaining endpoints and referenced
anchors. `enabled_only=True` restricts cleanup to enabled nets.
Related unresolved constraints can block removal before mutation.

`RemovedRoutePoint` is an immutable record containing `line`, detached
`point` and original zero-based `position`, for inspection/undo.
This operation does not snap components, route wires or follow moved pins.

## Source inspection

### Syntax views

```text
read_source(path, *, format=None, family=None, report=None, label=None, **options) -> Document
parse_source(data, *, format, family=None, report=None, label=None, **options) -> Document
document.as_schematic(*, report=None, label=None) -> Document
```

`read_source()`/`parse_source()` expose ASC/XML syntax without normal
semantic import. DCH already uses the shared model. `as_schematic()`
normalizes a syntax view for semantic editing/conversion; on an existing shared
model it returns an independent clone.

```python
from lib import read_source

source = read_source("design.asc")
current = source.as_schematic()
```

### Direct format entry points

| Function | Result |
| --- | --- |
| `read_asc(path, *, encoding=None)` | ASC syntax document |
| `parse_asc(text, *, source=None)` | ASC syntax document |
| `read_dchxml(path)` | XML syntax document |
| `parse_dchxml(data, *, source=None)` | XML syntax document |
| `parse_dch(data, *, report=None, label=None, **options)` | Shared schematic document, accepting DCH reader options |

Prefer unified `read()`/`parse()` for ordinary work and a uniform
context/report contract.

### Output projections

`document.as_asc()` and `document.as_dchxml()` return independent output
syntax documents. Both accept keyword `context=None`, `report=None`,
`label=None` and `version` (the destination default when omitted).
The resulting field structure is format-specific.

On an explicitly loaded ASC source view, `preserve=True` can retain syntax
and whitespace. This is not binary-chunk preservation in the editable model.

### Element inspection and adapter operations

| Signature / attribute | Meaning |
| --- | --- |
| `Element(kind, *values, source=None)` | Low-level record constructor |
| `inspect()` | Shallow diagnostic dictionary |
| `source` | Optional source span |
| `annotations` | Diagnostic annotations |
| `items` | Mixed tuple of child elements and values |
| `arguments` | Tuple of `Value` wrappers |
| `values` | Tuple of primitive values |
| `scalar(name, default=None, occurrence=0)` | Lower-level occurrence-aware read |
| `set_argument(index, value)` | Replace a zero-based argument; return the element |
| `set_values(*values)` | Replace arguments; return the element |
| `set_field(name, *values, occurrence=0)` | Write syntax values; return the field element |
| `bind_schema(schema)` | Establish schema-bound storage; return the element |

These operations support adapters/syntax investigation; they are not substitutes
for validated named editing. Legacy `@N` predicates select zero-based syntax
arguments. Ordinary editing does not require them.

### Syntax value types

```text
Value(value, kind, unit="", lexeme=None, source=None)
Value.of(value, *, symbol=False, unit="") -> Value
SourceSpan(format, start, end, source=None)
```

Both types are immutable. `Value.of()` validates primitive values and turns
finite floats into decimals. Source spans/lexemes are optional descriptions;
they do not make original bytes authoritative after editing.

## Extensions and failures

### Adapter registration

```text
register_reader(format, reader) -> None
register_writer(format, writer) -> None
```

| Callback | Required interface |
| --- | --- |
| `reader` | `reader(path, **options) -> Document` |
| `writer` | `writer(document, path, **options)` |

Duplicate names and invalid registrations raise `ValueError`.
Registration extends file dispatch, not buffer parsing/serialization or
capability declarations. Registered document representations pass through
without schematic normalization.

### Exceptions

| Exception | Typical cause |
| --- | --- |
| `OSError` subclasses | File access failures |
| Syntax/decoding/encoding exceptions | Invalid input or unrepresentable output text |
| `KeyError` | Missing field read/deletion or unknown field write |
| `LookupError` | Unknown UID, or zero/multiple matches for `one()` |
| `TypeError` | Incompatible argument/field type, read-only assignment, required-field deletion |
| `ValueError` | Invalid selector/value/version/option |
| `UnsupportedFileError` | Unsupported file format, document family or version; subclass of `ValueError` |
| `ReferenceError` | Relationship constraint violation; library subclass of `ValueError` |
| `IncompleteDocumentError` | Complete output requested from partial data; subclass of `ValueError` |
| `NotImplementedError` | Unimplemented mapping, geometry case or required measurement service |

The library's `ReferenceError` is separate from Python's built-in exception
with that name. Conversion reports retain diagnostics while preserving the
original exception type.

`UnsupportedFileError` exposes `format`, `family` and `version` when known;
unavailable identity values are `None`. Its `reason` is `"format"` for an unknown
or unavailable format, `"family"` for a recognized unavailable document family,
or `"version"` for an unsupported revision. These attributes allow callers to
describe support limits without parsing an error message. Invalid family names
and ambiguous capability queries remain configuration errors (`ValueError`).

## Conversion limits

The current model may contain data a selected output cannot carry. The table
below summarizes important cases; the detailed implementation register remains
in [FORMAT_CAPABILITIES.txt](../references/FORMAT_CAPABILITIES.txt).

| Data | Current output consequence |
| --- | --- |
| Fractional fonts / monospacing | DCH/XML schema 52 carry both. Earlier targets round sizes and omit monospacing with warnings. ASC carries fractional sizes but omits monospacing. |
| Persistent net IDs / drawing-pad links | DCH requires schemas 47 / 48 respectively; meaningful omitted values warn. |
| Simulator additions | DCH/XML schema 50 onward carry advanced/digital settings. Older targets and ASC omit some. XML 5.2 application readers reset digital arguments; this library retains them. |
| Picture flip | DCH schema 51 onward, XML target 52; other destinations warn when selected. |
| Old BitmapIndex without filename | Single-file input retains an unresolved reference. ASC can retain the index; DCH/XML warn and emit an unassigned picture unless supplied a filename mapping. |
| Marking appearance, title grids, supplier details, unused definitions | Some projections cannot retain every attribute; meaningful omissions warn. |
| ASC text / encoding | Quotes, line breaks and unsupported characters may be substituted with warnings. Receiving applications normalize some literal exclamation marks. |
| Schematic rotations | Export normalizes/rounds to quarter turns without changing authoring angles; footprint/3D domains remain separate. |

Unsupported mappings and invalid output are errors. Meaningful round trips use
the model and adapters, without source-byte replay. Equivalent output can differ
in bookkeeping, normalization or bounded text calculations; see
[regenerated binaries](../README.md#regenerated-binaries).
