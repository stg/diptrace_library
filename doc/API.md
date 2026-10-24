# API guide

Use `from lib import ...` from the repository directory containing `lib/`.
The supported document family is currently schematic. DCH, ASC and DCHXML
all import into the same `Document`; format choice belongs to input/output,
not to the editing code. See [getting started](GETTING_STARTED.md) for a short
introduction, [the model guide](MODEL.md) for design rules, and
[SCHEMATIC.md](SCHEMATIC.md) for every declared record and field.

The Python examples run in order in one session. They create their own small
design and write example files in the current directory.

- [Reading and writing](#reading-and-writing)
- [Versions](#versions)
- [Reports](#reports)
- [Fields and reflection](#fields-and-reflection)
- [Searching](#searching)
- [Reference designators](#reference-designators)
- [Construction and ownership](#construction-and-ownership)
- [Relationships](#relationships)
- [Configuration](#configuration)
- [Conversion limits](#conversion-limits)
- [Inspection and advanced operations](#inspection-and-advanced-operations)

## Reading and writing

```python
from lib import (
    ConversionReport, ExportContext, format_capabilities,
    new_schematic, new_symbol, new_pin, new_net, new_schematic_shape, new_wire,
    parse, read, serialize, write, schematic_schema,
)

design = new_schematic(sheet_name="Example")
components = design.one("/Schematic/Components")
part = components.append(new_symbol("Resistor", "R1"))
part["Value"] = "10k"
part["X"], part["Y"] = 15, 30
pin = part.child("Pins").append(new_pin())
pin["Number"], pin["StringNumber"] = 1, "1"

report = ConversionReport()
write(design, "example.dch", version=52, report=report)
loaded = read("example.dch", report=report)
assert loaded.one('/Schematic/Components/Part[RefDes="R1"]')["Value"] == "10k"

xml = serialize(loaded, format="dchxml", version=52, report=report)
converted = parse(xml, format="dchxml", report=report, label="XML round trip")
write(converted, "example.asc", report=report)
```

| Function | Result and options |
| --- | --- |
| `read(path, *, format=None, context=None, report=None, label=None, **options)` | Import a file into a `Document`; infer format from its extension unless supplied |
| `parse(data, *, format, context=None, report=None, label=None, **options)` | Import an in-memory buffer into a `Document` |
| `write(document, path, *, format=None, context=None, report=None, label=None, **options)` | Export to a file; return `None`; infer format from the output extension unless supplied |
| `serialize(document, *, format, context=None, report=None, label=None, **options)` | Export to `bytes`, including for text formats |

Paths may be strings or `pathlib.Path` objects. Format names are case insensitive
and accept a leading dot: `"DCH"` and `".dch"` select the same adapter.
Buffers are bytes; ASC and DCHXML also accept text strings. Only the supplied
input is read. Libraries and companion files are not opened implicitly.

All three outputs accept `version=`. Optional `context`, `report` and `label`
have the same meanings for files and buffers. Destination-specific options:

| Format | Import options | Export options |
| --- | --- | --- |
| DCH | `ansi_encoding="cp1252"` for pre-Unicode strings; `allow_partial=False`; `component_limit=None` | `version` and optional DCH context |
| ASC | `encoding=None` detects UTF-8 BOM, otherwise Windows-1252 | `encoding=None` uses the context encoding or Windows-1252; `preserve=True`, `allow_partial=False` are advanced syntax-view options |
| DCHXML | XML declaration controls byte decoding | `newline="\n"` or `"\r\n"`; byte output is UTF-8 |

Partial/limited DCH imports are for investigation, not complete conversion.
Normal writers reject incomplete designs. Explicit `allow_partial` ASC output
is an inspection escape hatch, not a completeness guarantee.

The document also provides format-specific methods:

| Method | Return |
| --- | --- |
| `to_dch_bytes(*, version=46, context=None, report=None, label=None)` | `bytes` |
| `to_asc(*, preserve=True, allow_partial=False, context=None, version=46, report=None, label=None)` | `str` |
| `to_asc_bytes(...)` | `bytes`; same options plus `encoding=None` |
| `to_dchxml(*, newline="\n", context=None, version=46, report=None, label=None)` | `str` |
| `to_dchxml_bytes(...)` | UTF-8 `bytes`; same options |
| `save_dch(path, ...)`, `save_asc(path, ...)`, `save_dchxml(path, ...)` | `None`; corresponding byte-output options |

Writers prepare a detached output view. They do not change authored values
to suit a destination. File output overwrites its supplied path and requires
the parent directory to exist. Applications can use temporary-file replacement
when they need atomic filesystem updates.

## Versions

Schema numbers are format revisions, not DipTrace application releases.
The [schematic support table](../README.md#schematics) gives the current ranges.
Use the capability query rather than duplicating those ranges in an application:

```python
capabilities = format_capabilities("dch")
assert capabilities.family == "schematic"
assert capabilities.supports_read(29)
assert capabilities.supports_write(52)
target = capabilities.output_version(52)
binary = serialize(design, format="dch", version=target, report=report)
```

`format_capabilities(format)` returns an immutable `FormatCapabilities` with
`format`, `family`, `read_versions`, `write_versions` and
`default_write_version`. `supports_read(version)` and `supports_write(version)`
return booleans. DCHXML input versions are vocabulary strings such as `"5.3"`;
DCHXML output versions are target schematic schema numbers, just as for DCH.

`output_version(requested=None, *, fallback=False)` selects the default when
omitted, otherwise requires exact support. With explicit `fallback=True`, an
unsupported integer request may select the highest supported earlier version.
It never upgrades. Unknown formats or unsupported choices raise `ValueError`.
A caller allowing fallback should report a changed choice. Capabilities describe
the adapter; particular designs can still lose data in a supported destination.

## Reports

`ConversionReport()` collects diagnostics in operation order across any number
of imports and exports. `ImportReport` and `ExportReport` are aliases of this
class. Recreate the object for an independent report, or call `report.clear()`
to empty it in place. Previously retrieved filtered lists are snapshots.

```python
report.clear()
try:
    serialize(design, format="dch", version=999, report=report, label="unsupported")
except ValueError:
    assert report.errors[-1].operation == "export"
    assert report.errors[-1].label == "unsupported"
else:
    raise AssertionError("An unsupported version must fail")

report.clear()
assert not report.notices
serialize(design, format="dch", version=52, report=report)
assert not report.errors
```

| Member | Meaning |
| --- | --- |
| `notices` | Ordered list of all `ConversionNotice` objects |
| `infos`, `warnings`, `errors` | New lists filtered by severity |
| `clear()` | Remove all collected notices; return `None` |

Information describes equivalent normalization or reconstructable output data.
A warning describes meaningful loss, unresolved data or deferred normalization.
Errors still raise the original exception; attaching a report does not permit
invalid conversion to continue. Reports contain diagnostics, not entries for
operations that finish without a notice.

`ConversionNotice` is immutable. It exposes `rule` (machine-readable rule name),
`message`, `severity` (`info`/`warning`/`error`), `operation`
(`import`/`export`), `format` (also available as `destination`),
`paths` (tuple of affected record paths), `recoverability`, `file` and `label`.
`file` is the supplied path or `None` for a buffer. The optional caller label
helps attribute buffers or batch operations.

Without a report, information stays quiet and warnings are Python
`ConversionWarning` instances. Their `notice` attribute contains the structured
notice. Python's `warnings` module can filter or log them.

## Fields and reflection

Fields follow Python mapping conventions. Both assignment forms below use the
same validation and reference maintenance:

```python
part["Value"] = "22k"
assert part.get("Value") == "22k"
assert part.set("Value", "47k") is None
part["Datasheet"] = "https://example.org/resistor"
assert "Datasheet" in part
del part["Datasheet"]
assert part.get("Datasheet", "") == ""

definition = part.schema.field("Value")
assert definition.name == "Value"
assert "Value" in schematic_schema()["Part"].fields
for name, field in part.schema.fields.items():
    if name in part and not field.readonly:
        value = part[name]       # Dynamic access follows the ordinary rules.
```

| Operation | Behavior |
| --- | --- |
| `record[name]` | Read a field; missing/unknown names raise `KeyError` |
| `record.get(name, default=None)` | Read, returning the default only if absent |
| `record[name] = value` / `record.set(name, value)` | Validated assignment; `set` returns `None` |
| `name in record` | Presence, including present `None`, `False`, zero and empty text |
| `del record[name]` | Remove an optional field; missing names raise `KeyError` |
| `record.child(name)` | Navigate to the first child record/container or `None` |

Assigning `None` differs from removal and requires a nullable definition.
Required fields cannot be removed. Unknown writes raise `KeyError`; read-only
assignment or child-container field access raises `TypeError`. Invalid edits
fail before mutation. Tuple fields read/write as tuples and expose named members
through their child record, for example `part.child("ShowRefDes")["Align"]`.
Integer fields reject booleans and fractional numbers; numbers must be finite.

`record.schema` is an immutable `Record` definition, or `None` for untyped
syntax. `schematic_schema()` returns an immutable name-to-record mapping without
a document. Definition types are available from `lib.common.schema`:

| Definition | Public description |
| --- | --- |
| `Record` | `name`, `description`, `fields`, `children`; `field(name)` raises `KeyError` for unknown fields |
| `Field` | `name`, `kind`, `required`, `nullable`, `default`, `unit`, `description`, `readonly`, `members`, `item_kind`, `length` |
| `Child` | `name`, `record` (allowed types), `minimum`, `maximum` (`None` means unbounded) |
| `MISSING` | Sentinel meaning no schema fallback |

A schema fallback is not an implicit `get()` value. `Field.validate(value)`
validates a proposed value. `Record.validate_fields(record)` and
`validate_children(record)` audit that part of a tree; normally use
`document.validate()` for a full audit. Definition parameters, callbacks and
dependencies support adapters; application edits should use named access.

## Searching

`Document` and `Element` provide `select(path, *, where=None)` and
`one(path, *, where=None)`. `select` returns a list in tree order.
`one` raises `LookupError` unless exactly one final match remains.

| Selector | Meaning |
| --- | --- |
| `/Schematic/Components/Part` | Placed components from the document root |
| `Pins/Pin` | Relative children from an element |
| `//Part` | Descendants named Part, including cached definitions |
| `*` | Any child name |
| `Part[2]` | Second matching child of each selected parent; one-based ordinal |
| `Part[RefDes="R1"]` | Exact text equality |
| `Part[Enabled=true]` | Boolean equality; `false` is also accepted |
| `Part[Page=0]` | Numeric equality |
| `/` | The document's outer root |

Use either quote style for text. Double a matching quote inside a literal,
for example `Part[Name='Jack''s connector']`. There is one predicate per step.
There are no ranges, boolean expressions, regular expressions, parent axes or
full XPath semantics. Invalid/unsupported syntax raises `ValueError`.
Exact text predicates distinguish `R003` and `R3` even though RefDes numbering
treats them alike.

Use a Python callable for richer comparisons. `where` runs on final matches
before `one` checks cardinality and preserves their order. Predicate errors
propagate; a non-callable `where` raises `TypeError`.

```python
selected = design.select(
    "/Schematic/Components/Part",
    where=lambda p: p["Page"] == 0 and 0 <= p["X"] <= 30 and 0 <= p["Y"] <= 30,
)
assert selected == [part]
assert design.one("//Part", where=lambda p: p.get("Value") == "47k") is part
assert part.find_all("Pin", recursive=True, where=lambda p: p["Number"] == 1) == [pin]
```

This tests stored placement origins in shared units, not visible bounds or
intersection with symbol geometry. There is no geometric selection API.

`document.find_all(kind, *, where=None)` searches recursively.
`element.find_all(kind=None, *, recursive=False, where=None)` defaults to direct
children. `children(kind=None)` returns a new list, `child(kind)` / `find(kind)`
returns the first child or `None`, `walk(include_self=False)` iterates depth
first, and `descendants(kind=None)` returns a list.
Results contain the actual editable records.

## Reference designators

`document.refdes(prefix)` returns a live `RefDesFamily` view of enabled physical
components across all sheets. Logical symbols and cache definitions are excluded.
Matches return records; numbering returns strings and does not reserve a name.

```python
resistors = design.refdes("R")
assert resistors.matches("R001") == [part]
assert "R0001" in resistors
assert resistors.first() == resistors.last() == "R1"
assert resistors.first_free() == "R2"
assert resistors.next("R1", mode="number") == "R2"
assert resistors.next("R0", mode="existing") == "R1"
assert resistors.previous("R2", mode="free") == "R0"

duplicate = design.copy(part, parent=components, fields={"RefDes": resistors.first_free()})
assert resistors.designators() == ["R1", "R2"]  # Reads the current design.
```

| Method | Result |
| --- | --- |
| `matches(reference=None)` | All matching items, including multipart units; ordered by number, spelling, then source order |
| `designators()` | Distinct authored spellings in numeric order |
| `reference in family` | Whether its numeric identity is occupied |
| `first()`, `last()` | Lowest/highest existing spelling, or `None` |
| `first_free(start=1)` | First free counter at/above a nonnegative integer |
| `next(reference, *, mode)`, `previous(reference, *, mode)` | Strictly following/preceding `number`, `existing` name or `free` counter |

`mode` is required. `existing` returns `None` without a match; `previous`
stops at zero. Generated names are unpadded; existing names retain spelling.
Invalid modes, counters or names raise `ValueError`.

Identity is the exact case-sensitive prefix plus final consecutive ASCII digits.
`R003` equals `R3`; a bare prefix means zero, so `R`, `R0` and `R000`
are equivalent. `R-1` is prefix `R-` and counter 1.
`R1-X12` belongs to `R1-X`; `R1-12` belongs to `R1-`.
Punctuation stays literal. Counters are never negative.

Named edits reject occupied identities atomically. Identically named multipart
units may coexist; these helpers do not coordinate renaming an entire group.
A spelling change such as `R003` to `R3` is valid when unshared.
Existing managed property-copy relationships still follow valid edits.

For lists or other record types:

```python
from lib import RefDesFamily, split_refdes

assert split_refdes("R1-X012") == ("R1-X", 12)
family = RefDesFamily("R1-X", ["R1-X1", "R1-X003"])
assert family.designators() == ["R1-X1", "R1-X003"]
assert family.first_free() == "R1-X2"
assert family.previous("R1-X4", mode="existing") == "R1-X003"
```

`RefDesFamily(prefix, references, *, get_refdes=None)` snapshots an iterable,
or calls a supplied zero-argument callable for live items. `get_refdes(item)`
extracts names from non-string items. Prefixes cannot end in an ASCII digit.
Empty stored names are unassigned and skipped; `split_refdes("")` raises.
Ordinary spaces are rejected by helpers and named RefDes edits. Imports do not
silently rewrite source names; queries encountering incompatible stored names
raise rather than falsely freeing a possibly occupied number.

## Construction and ownership

Constructors return detached records except `new_schematic`, which returns
a document with a page, standard settings and empty collections.

| Constructor | Meaning |
| --- | --- |
| `new_schematic(sheet_name="Sheet 1")` | New schematic `Document` |
| `new_symbol(name="", reference="", placed=True)` | Component, or cached definition with `placed=False` |
| `new_pin(index=0, placed=True)` | Pin, or cached pin; attached index follows collection order |
| `new_net(name="")` | Net with empty member/wire collections |
| `new_wire(bus=False)` | Wire or bus line with empty points and unassigned endpoints |
| `new_schematic_shape(index=0)` | Sheet drawing with editable points/text |

Set meaningful fields, then attach to the appropriate collection. Assigning a
library filename does not load that library or replace a definition. Constructors
do not route wires or calculate fills.

```python
drawing = design.one("/Schematic/Shapes").append(new_schematic_shape())
drawing["Type"] = 1
for x, y in ((0, 15), (30, 15)):
    point = drawing.child("Points_New").add("pt")
    point["X"], point["Y"] = x, y

duplicate.move_to(components, index=0)
assert components.children("Part")[0] is duplicate
design.remove(duplicate)
assert resistors.designators() == ["R1"]
design.validate()
```

| Operation | Ownership and return |
| --- | --- |
| `parent.append(node)` / `parent.insert(node, index=None)` | Attach a detached node; return it. Index is zero-based child order. |
| `parent.add(kind, *values)` | Construct and attach an `Element`; return it. Prefer constructors for domain objects. |
| `node.move_to(parent, index=None)` | Move/reorder the same record with its links; return it |
| `node.detach()` / `parent.remove(node)` | Detach conservatively; dependencies may block it; return the node |
| `document.copy(node, *, parent=None, index=None, fields=None)` | Copy content and owned links; return the copy. Default to the original's parent, appending unless an index is supplied. Apply root field overrides before attachment. |
| `document.remove(node)` | Remove a subtree and its owned links; return the detached node. External users/scopes may block it. |
| `node.clone()` | Detached tree copy with fresh UIDs, without arbitrary graph links |
| `document.clone()` | Independent full design, including its relationship graph, with fresh record UIDs |

Copying remaps internal targets and retains external targets. Incoming users stay
on the original: copying a component does not copy a net's memberships.
Structural edits preflight ownership, keys, cardinality and scopes. A move cannot
give a node two parents or split a protected attachment segment. Multiple API
calls are separate edits, not a transaction with automatic rollback.

## Relationships

Use semantic relationship fields when provided. A net's ordered members own pin
identities; `pin["Net"]` is its editable reverse view. Serialized component/pin
positions follow those identities automatically.

```python
net = design.one("/Schematic/Nets").append(new_net("SIGNAL"))
pin["Net"] = net
assert pin["Net"] is net
membership = design.references.incoming(pin, role="net-member")
assert len(membership) == 1

second_pin = part.child("Pins").append(new_pin())
second_pin["Number"], second_pin["StringNumber"] = 2, "2"
replacement = design.references.retarget(membership[0], second_pin)
assert replacement.uid == membership[0].uid
assert second_pin["Net"] is net
assert pin["Net"] is None
second_pin["Net"] = None
assert not design.references.incoming(second_pin, role="net-member")
```

Wire constraints may prohibit membership changes; changing a relationship does
not move attached geometry. Named property edits update bound text and managed
copies while literal text stays independent.
See [ownership and relationships](MODEL.md#ownership-and-relationships).

`document.references` is a `References` graph. Iterate it for immutable
`Reference` objects; `len(graph)` counts resolved links.

| Method/property | Meaning |
| --- | --- |
| `get(uid)` | Current link by identity; unknown identity raises `LookupError` |
| `incoming(target, *, role=None)` / `outgoing(source, *, role=None)` | Lists of links, optionally filtered by role |
| `retarget(reference, target)` | Validate/change target; return a replacement `Reference` with the same UID |
| `discard(reference)` | Remove binding subject to domain constraints; remaining literal fields are not a new resolved relationship |
| `issues` | Unresolved-reference records with retained identities/scopes |
| `validate()` | Audit consistency without inventing missing targets |

A `Reference` exposes `uid`, `source`, `target`, `role`, `indices`
and `guards`. A target is an element or `Segment(start, end)` pair of adjacent
route points. After retargeting, use the returned object or `graph.get(uid)`.
`UnresolvedReference` has `source`, `message`, `indices`, `collections`
and `guards`. Its scope prevents edits from silently reinterpreting an identity.

Advanced adapter/custom-model code can use
`bind(source, target, *indices, role="", guards=(), preserve=False)`:

| Projection/guard | Meaning |
| --- | --- |
| `Index(field, argument=0, ancestor=0, offset=0)` | Project target collection position, optionally from an ancestor |
| `Key(field, name="Id", argument=0, ancestor=0)` | Project a unique named target key |
| `Property(field, name=None, argument=0, ancestor=0, target_argument=0)` | Copy a target property/tuple member without requiring uniqueness |
| `Guard(field, values)` | Require a controlling field to keep an allowed value |
| `OrdinalGuard(field, member)` | Keep the member within an inclusive active-prefix limit |

`field` is the field's child element, `argument` is its zero-based slot, and
`ancestor` climbs from the target before projection. `preserve=True` requires
existing values to agree instead of initializing them. Custom binding does not
extend a file adapter's vocabulary. `manages(field, argument=0)` and
`unresolved_slot(field, argument=0)` inspect ownership of a projection slot.
`note(source, message, *indices, collections=None, guards=())` records an
unresolved identity; `discard_issue(issue)` explicitly removes its constraint.
Do not edit the issues list directly.

## Configuration

Contexts are frozen dataclasses. Construct defaults directly;
use `dataclasses.replace` for a modified copy. Export overrides take precedence
over stored settings, then standard defaults: mm, vector text and font size 2.
Editable lengths always use shared units.

```python
from dataclasses import replace

effective = ExportContext().resolved(design, format="dchxml")
in_mils = replace(effective, units="mil")
xml_in_mils = serialize(design, format="dchxml", version=52, context=in_mils, report=report)
assert design.one('/Schematic/Components/Part[RefDes="R1"]')["X"] == 15
```

`ExportContext(...).resolved(document, *, format=None)` returns independent
effective choices; `format` selects the destination context. Specialized
contexts use `resolved(document)`. Resolve for the actual destination:
transferring resolved choices may include options another format cannot hold.

| Common export field | Default / meaning |
| --- | --- |
| `units` | `None`: stored display units, then mm; override `mm`, `mil`, `in`/`inch` |
| `project_dir` | `None`: stored ProjectDir, then empty text; no directory lookup |
| `marking_style` | `None`: stored/default choices; optional `MarkingStyle` |
| `grid_snap` | `None`: stored choice, then true; explicit DCH override is rejected |
| `text_layout` | Default `TextLayout` service |
| `use_part_font_color` | `None`: stored choice, then false |
| `additional_user_fields` | `()`: extra global rows `(display_name, key, state, position)` |
| `legacy_picture_files` | `None`: filename tuple indexed by old unresolved BitmapIndex; no files opened |
| `path_variables` | `None`: explicit `PathVariables` configuration |
| `refresh_user_fields` | `False`: opt in to refreshing global user-field choices on the output view |

| Context | Destination additions |
| --- | --- |
| `DchExportContext` | `compact_inactive=None` resolves false; `default_main_supplier=False` supplies a missing old supplier-match flag |
| `AscExportContext` | `compact_inactive=None` resolves true; same supplier default; `encoding=None` resolves Windows-1252; `line_width=None` resolves the standard pen-width callback; `legacy_text_slots=None` optionally supplies two modes, two alignments, two field names |
| `DchXmlExportContext` | `active_sheet=None` follows stored page selection, then page zero |

Unsupported explicit choices raise. Compaction cannot discard referenced content.
Reports describe omissions and other adaptations. ASC's `line_width(layer)`
callback returns a physical width in shared units; the default returns 0.1.

`ImportContext(font_size=2, font_name="", text_layout=None)` supplies missing
legacy DCH environment choices; stored settings take precedence. `font_size`
is a positive integer; `layout` returns the supplied/default service.
Other normal formats accept the context argument but do not currently need
these DCH modernization settings.

Optional layout types are imported from their owning modules:

- `lib.schematic.layout.markings.MarkingStyle`: `font_size=2`,
  `font_name=""`, `vector=True`, `font_width=-2.0`, `font_scale=1.0`,
  `font_color=0`, `pen_width=1.0`, `mono=False`.
- `lib.schematic.layout.text_layout.TextLayout`:
  `measure_system=None`, `resolution=10.0`, `font_scale=1.0`.
  System measurement receives `(text, family, point_size)` and returns an object
  with pixel `width`/`height`. Resolution/scale must be finite and positive.
  `symbol_bounds(shape)` returns text-box corners.
- `lib.common.text.windows.WindowsFontMetrics(dpi=96)` is a read-only Windows
  backend; pass `.measure` as the callback. Other systems can supply a service.

Vector layout is self-contained. The default service loads Windows measurement
lazily only when system text needs it. A required unavailable backend raises.

`PathVariables` accepts `main_dir=""`, `program_docs=""`, `my_docs=""`,
`standardlibs=True`, `maindir=True`, `programdocs=True`, `mydocs=True`,
and `custom=()` rows `(name, value, enabled)`.
`select(variable, actual, *, project_dir="", include_project=True)` returns
the selected output spelling. Configuration does not read environment variables,
the registry or directories. Cyclic/excessive expansion raises `ValueError`.

## Conversion limits

Imports modernize; output versions adapt a detached view. Review reports when
changing format/version. Important current cases:

| Data | Current consequence |
| --- | --- |
| Fractional fonts / monospacing | DCH/XML schema 52 carry both. Earlier targets round fractional sizes and omit monospacing with warnings. ASC carries fractional sizes but omits monospacing. |
| Persistent net IDs / drawing-pad links | DCH output requires schemas 47 / 48 respectively; omitted meaningful values warn. |
| Simulator additions | DCH/XML schema 50 onward carry advanced/digital settings. Older targets and ASC omit some. XML 5.2 application readers reset digital arguments; our reader retains them. |
| Picture flip | DCH schema 51 onward, XML target 52; other destinations warn when selected. |
| Old BitmapIndex without filename | Single-file input retains an unresolved reference. ASC can retain the index; DCH/XML warn and emit an unassigned picture unless a filename mapping is supplied. |
| Marking appearance, title grids, supplier details, unused definitions | Some projections cannot retain every attribute; meaningful omissions warn. |
| ASC text / encoding | Quotes, line breaks and unsupported characters may be substituted with warnings; receiving applications also normalize some literal exclamation marks. |
| Schematic rotations | Export normalizes/rounds to quarter turns; authoring angles stay intact. Footprint/3D angles have separate rules. |

Unsupported mappings and invalid output are errors. Round trips preserve
meaningful facts through the model and adapters, without replaying binary chunks.
Equivalent output can differ in bookkeeping, normalization or bounded text
calculations. See [regenerated binaries](../README.md#regenerated-binaries).

## Inspection and advanced operations

### Document state and validation

`Document(root=None, *, representation="tree")` is the low-level constructor.
Prefer `new_schematic()` to obtain domain defaults and an editable schematic.
`document.root` is the outer element; `representation` identifies its API view
(`schematic` for normal imports). `complete` reports completeness,
`diagnostics` holds diagnostic strings, and `metadata` holds optional
inspection/provenance data. Metadata is not export configuration.

`document.get(uid)` resolves an element identity or raises `LookupError`;
it differs from a record's default-aware `get(name)`.
`validate()` audits fields, ownership and references without changing facts,
returning `None`. Intact unresolved identities may remain.
`references.issues` lists graph issues; `unresolved()` separately returns
document diagnostics and incomplete-record annotations.

Ordinary edits/saves need no rebuild. Advanced `rebuild(*, force=True)`
validates and projects compatibility indices, returning a UID-to-element dict.
`rebuild_index()` constructs only that dictionary. Neither repairs identities
or moves geometry.

### Source syntax

`read_source(path, *, format=None, report=None, label=None, **options)` and
`parse_source(data, *, format, report=None, label=None, **options)` expose
syntax. ASC/XML retain syntax trees; DCH already uses the shared model.
Call `as_schematic(*, report=None, label=None)` before semantic conversion;
on a shared model it returns an independent clone.

```python
from lib import parse_source

syntax = parse_source(serialize(design, format="asc", report=report), format="asc")
assert syntax.representation == "asc"
normalized = syntax.as_schematic(report=report)
assert normalized.representation == "schematic"
assert normalized.one('/Schematic/Components/Part[RefDes="R1"]')["Value"] == "47k"
```

`read_asc(path, *, encoding=None)` / `parse_asc(text, *, source=None)` and
`read_dchxml(path)` / `parse_dchxml(data, *, source=None)` are low-level
syntax functions, not aliases for normal import.
`parse_dch(data, *, report=None, label=None, **options)` returns the shared
model with DCH reader options. Prefer `read`/`parse` for uniform diagnostics.

`as_asc(*, context=None, version=46, report=None, label=None)` and
`as_dchxml(...)` project independent output syntax documents. Their structure
is format-specific. ASC `preserve=True` can retain syntax in a source view;
that is separate from the editable model.

### Element inspection

Elements expose `uid`, `kind` (`type` is an alias), `parent`, `path`,
`changed`, `schema`, `source` and `annotations`. Paths follow ordering;
UIDs survive moves and are fresh in clones. `changed` includes descendants,
but is not a persistent revision/hash. `inspect()` returns a shallow dictionary.

Adapter/syntax operations include `Element(kind, *values, source=None)`,
`items` (mixed tuple), `arguments` (tuple of `Value`), `values` (primitives),
`scalar(name, default=None, occurrence=0)`, `set_argument(index, value)`,
`set_values(*values)`, `set_field(name, *values, occurrence=0)` and
`bind_schema(schema)`. These are lower-level operations, not substitutes for
validated named editing. Legacy `@N` selector predicates address zero-based
syntax arguments; normal editing does not need them.

`Value(value, kind, unit="", lexeme=None, source=None)` and
`SourceSpan(format, start, end, source=None)` are immutable syntax descriptions.
`Value.of(value, *, symbol=False, unit="")` builds validated primitive wrappers;
floats become finite decimals. Optional spans/lexemes do not make source bytes
authoritative after editing.

### Geometry helpers

| API | Result / limits |
| --- | --- |
| `Bounds(left, top, right, bottom)` | Immutable bounds; `width`, `height`, `center`, `union(other)` |
| `Bounds.from_points(points)` | Bounds or `None` when empty; nonfinite coordinates fail |
| `circular_arc_bounds(start, middle, end)` | Arc bounds including cardinal extrema |
| `ellipse_points(first, opposite, *, segments=30, closed=False)` | Tuple of samples; at least three segments; `closed` repeats the first |
| `symbol_bounds(part)` | Local enabled-pin/non-text-drawing bounds; excludes placement, rotation, pen width and labels |
| `pattern_bounds(pattern)` | Local pad/hole/non-text-drawing bounds; unsupported contours/rotations raise `NotImplementedError` |
| `coalesce_routes(document, *, enabled_only=False)` | Remove excess coincident wire points, protect anchors; return tuple of `RemovedRoutePoint(line, point, position)` |

The route helper returns detached points and original zero-based positions for
inspection/undo. It does not route, snap components or follow moved pins.
Related unresolved constraints can block removal.

### Adapter registration and exceptions

`register_reader(format, reader)` registers `reader(path, **options) -> Document`.
`register_writer(format, writer)` registers `writer(document, path, **options)`.
Duplicate/invalid registrations raise `ValueError`. Registration extends file
dispatch, not buffer operations or capability declarations. Registered document
representations pass through without schematic conversion.

File I/O raises ordinary `OSError` subclasses. Invalid selectors/versions/values
generally raise `ValueError`; wrong types raise `TypeError`. Missing fields
raise `KeyError`; unique lookups raise `LookupError`.
`ReferenceError` is the library's `ValueError` subclass for relationship
constraints, not Python's built-in weak-reference exception.
`IncompleteDocumentError` rejects complete output from partial data.
Parsers can raise specific syntax/decoding exceptions; reports preserve their
original types while collecting diagnostics.
