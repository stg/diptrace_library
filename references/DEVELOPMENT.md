# Library development

## Completed: examples and model usability

- [x] Provide common runnable examples under `examples/schematic/`, using small,
  self-contained public designs. Keep a small, curated set that covers the common
  tasks below; combine related tasks rather than creating an example for every
  API variant or format combination. Cover:
  - Reading DCH, ASC and DCHXML into the common model; inspecting components,
    pins, nets, fields and references.
  - Searching and bulk editing component values and user fields.
  - Cloning, moving and reordering records, retargeting references and rebuilding.
  - Creating a small schematic and adding drawing data.
  - Converting between the three formats, choosing output versions, supplying
    optional context and reviewing import/export reports.
  Prefer named bracket access and assignment in examples (`part["Value"]`,
  `part["Value"] = "22k"`). Use `get(name, default)` when a fallback read is
  intended, and named membership tests when presence itself matters. Show the
  explicit `get`/`set` equivalents where that helps explain dynamic access.
  Keep primary documentation readable for library users. Explain each concept
  once, with only the examples needed to use it; leave exhaustive combinations
  and edge-case coverage to tests and supporting references.
  Keep examples focused on data editing and verify their observable results with
  portable checks. Higher-level editing remains deferred; examples may mention
  future coordinated connection editing, trace following or pour calculation
  when explaining the current scope.
  - Record friction found while writing or using each example as actionable
    improvement items in this list: awkward queries, missing named access,
    repetitive construction, unclear units, reference handling, diagnostics or
    documentation gaps. Include the triggering task and desired behavior.
    - Resolved construction friction: fresh pins now acquire canonical membership
      semantics on attachment, before dependent NetNumber copies can be created.
      New subtrees activate recognized links with targeted schema/reference plans;
      import assembly keeps its internal boundary. Portable activation tests cover
      the original probe and combined index/membership failures.
    - Resolved editing friction: assigning RelatedNet on an attached drawing now
      activates its link through the prospective field plan. Controller changes
      include nested sources and propagated target constraints, without a full
      binder pass. Invalid edits preserve values and graph topology together.
    - Resolved example friction: new nets include recent-version identity data;
      common contexts can resolve defaults for a selected output format before
      customization. Three examples exercise creation, editing and conversion.
  - Prefer generic improvements to the model, API or documentation that benefit
    other callers. Avoid solving friction only inside an example with ad hoc
    helpers. Distinguish current data-editing gaps from deferred higher-level
    operations; recording an item does not bring those operations into scope.

- [x] Define and document a model with named fields and a consistent editing API.
  - Give every meaningful field a declared name, including values currently
    accessed as positional arguments. Public ASC/DCHXML vocabulary guides names;
    neither format's serialized layout defines the shared model.
  - Support both `get(name, default=None)` / `set(name, value)` and named bracket
    access (`record[name]`, `record[name] = value`) through the same field lookup
    and mutation implementation. Reading an existing field is equivalent in
    either form; `get` supplies a default for a missing field, while
    bracket reads raise `KeyError`. Both assignment forms apply identical type
    validation, reference maintenance, change tracking and cache invalidation.
    Reject unknown field names on assignment and invalid values promptly. Keep child
    navigation and record queries separate from field reads.
  - Support removing optional fields with `del record[name]`. Reject deletion of
    required fields and honor reference/dependency constraints before making
    changes. Use the same coherence, change-tracking and cache-invalidation
    machinery as assignment. A missing field, including an unknown name, raises
    `KeyError`. Deletion means absence, independently of assigning
    `None` where the schema allows a nullable value. Writers generate any
    required destination defaults on their detached view.
  - Follow Python mapping conventions for missing-value behavior: `get(name)`
    returns `None` for a missing field, and `get(name, default)` returns the
    supplied default, including for names not declared by the schema.
    A present nullable value of `None` remains `None`; membership distinguishes
    that state from absence. Unknown names are absent for membership tests and
    raise `KeyError` on bracket reads. Schema reflection can check whether a name
    is declared; schema validation rejects unknown writes and required-field
    deletion without changing the ordinary mapping lookup conventions.
  - Support named membership checks (`"Datasheet" in record`) for whether a field
    is present, independently of its value's truthiness. Distinguish present
    values such as `0`, `False` and empty text from absence. Schema reflection
    separately describes whether a field is declared for that record type.
  - Let schema-based reflection discover fields and inspect their definitions,
    using the same named access and mutation path for dynamic reads and writes.
    Reflection must preserve the normal validation and coherence guarantees.
  - Support named selector predicates such as `//Part[RefDes="R12"]`. Ordinary
    editing must not require `@N`, `values[N]` or `set_argument(N, ...)`.
    Positional file layouts belong in adapters; explicit source inspection can
    expose their syntax separately. Meaningful collection ordering remains.
  - Make these actual schema definitions, rather than convenience aliases over
    undocumented positions. Maintain one authoritative value per fact; adapters
    generate the positional representation required by each file format.
  - Let the model schema own record and field definitions. Remove the validator's
    dependence on ASC projection field lists; adapters should consume the model
    definitions where appropriate.
  - Update callers, selectors, examples and tests together. Plan the transition
    from `scalar`/`set_field` and positional access explicitly, preserving format
    behavior and reference safety throughout the change.

Field access is implemented for supported schema-bound records:

```python
part = document.one('//Part[RefDes="R1"]')
part["RefDes"]
part.get("Datasheet", "")
part["RefDes"] = "R12"
part["Value"] = "22k"
"Datasheet" in part                 # Presence, including an empty value
del part["Datasheet"]                # Remove an optional field
pins = part.child("Pins")
```

- [x] Align the public reading, writing, reporting and configuration APIs.
  - Review file-based and in-memory operations together: `read`/`parse`, `write`,
    document save/serialization methods and format-specific entry points. Make
    equivalent operations follow predictable naming, signatures, defaults,
    accepted inputs and return-value conventions.
  - Use consistent report attachment across imports and exports, including
    conversions using one report for both operations. Keep operation/format
    labels, severity handling, exceptions and behavior without a supplied report
    coherent across entry points.
    Keep reports reusable across multiple imports and exports, appending notices
    in order. Make each notice attributable to its particular operation and
    input/output file or caller-supplied label for in-memory work. Document that
    an operation with no notices is not currently recorded as a success entry;
    a diagnostics collection and an operation history are different contracts.
  - Review the names and responsibilities of contexts/configuration objects.
    Distinguish persistent document settings, per-operation configuration,
    destination/version choices and environment services. Choose terminology
    callers can understand without knowing an adapter's implementation.
  - Keep configuration optional for ordinary work. Define consistent precedence
    for explicit arguments, configuration overrides, stored settings and standard
    defaults where each applies. Shared choices should have shared names and
    meanings; format-specific options should be clearly identified. Unsupported
    combinations must fail clearly rather than being silently ignored.
  - Include modest quality-of-life improvements that make common tasks easy.
    Provide a discoverable way to obtain default configuration and, where
    relevant, inspect the effective choices for a document and destination, then
    derive an independently customized configuration. Existing context constructors,
    export `resolved(document)` methods and standard dataclass replacement already
    provide parts of this; consolidate and document them before adding helpers.
    Distinguish inherited choices from resolved values, preserve validation, and
    keep customization from changing shared defaults or another operation.
    Let concrete example friction justify small additions; keep the public API
    compact and avoid unnecessary configuration machinery or competing shortcuts.
  - Keep output format, document kind and target version distinct as support
    grows. Ordinary use should not require configuration classes named after
    another format, such as supplying an ASC context for DCH output.
  - Keep reports as diagnostics, configuration as operation choices, and the
    editable design as the owner of design facts. Preserve detached export
    adaptation and the single-input-file import boundary.
  - Demonstrate the aligned API with equivalent file and in-memory examples,
    including defaults, overrides, shared reports and handled failures. Record
    migration from overlapping existing entry points and configuration classes;
    avoid adding another competing API alongside them.

- [x] Make model coherence automatic during ordinary data editing.
  - Implemented: prospective validation and incremental propagation through
    property/key copy chains, including bound text. Existing relationship mode
    guards cover resolved and unresolved links; conflicting edits fail atomically.
    Structural insertion, removal, reordering and moves now preflight affected
    references and update projections incrementally. Attachment activates known
    new-record relationships. Named edits also activate newly meaningful links;
    controller changes include nested sources and propagated target constraints.
    Active cache prefixes expand incrementally; shrinking or reordering cannot
    silently deactivate an existing link. Document.copy remaps owned links and
    Document.remove disposes of owned links atomically, protecting external users.
    Declared calculated-property dependencies also cover graph addition,
    retargeting, removal and collection-size changes. Named Property/Key links
    can select calculated fields without positional arguments. First membership
    assignment and disconnection preflight the combined operation atomically.
  - Audit facts and relationships currently represented in multiple places.
    Give each one an authoritative owner and derive reverse lookups, displayed
    values and file-format occurrences from it. Start with pin/net membership:
    callers must not maintain a pin's net assignment and a net's member list
    independently.
  - Keep identity-based links valid through renaming, reordering and retargeting.
    Refresh dependent properties and calculated displays as needed; preserve
    independently authored text even when it happens to match an old name.
  - Maintain affected invariants automatically for supported edits, without a
    whole-document rebuild, scan or clone on every mutation. Invalid operations
    should fail before leaving partial changes. Bulk construction/editing may
    use an explicit scope with a clear consistency boundary.
  - Separate model validation, internal lookup/cache maintenance and generation
    of file-format indices. Define a clear contract for each. Ordinary semantic
    reads, searches, edits and saves must not require callers to remember a
    `rebuild()` call. Writers already own detached output preparation.
  - Provide an explicit full-model validation/audit operation. Review whether
    `rebuild()` remains an advanced projection operation or can become internal;
    document current behavior and the migration from existing callers.
  - Preserve the existing reference, unresolved-identity and topology guards.
    Relationship coherence is data-model work; geometric wire following,
    routing and pour calculation remain deferred.

- [x] Audit and improve speed across the model, readers and writers.
  - Measured all six semantic read/write paths on small, medium and large
    designs, plus lookup scaling and cache memory. Retained bounded selector
    syntax caching, private lookup/reference indexes, ASCII conversion fast
    paths and lower-allocation field validation. Output comparisons and edit
    safety tests cover these changes; further optimization remains incremental.
  - Review every supported reader and writer for straightforward optimizations,
    as well as queries, edits, validation, reference handling, cloning and export
    preparation. Look for repeated tree/graph scans, repeated field lookup,
    unnecessary list/object allocation, redundant conversion and repeated work
    inside record loops.
  - Use representative small, medium and large inputs to establish where time
    and memory go and compare meaningful before/after results. Start with
    low-hanging improvements and avoid repeating expensive corpus work without
    a concrete need.
  - Maintain internal indexes and caches when useful: identities, references by
    source/target, field lookup and calculated results. These are implementation
    details, conventionally named with a leading underscore in Python, even if
    stored on model objects. They are not additional authored design facts or
    public editable fields and must not be serialized as such.
  - Update cheap indexes incrementally. Invalidate expensive calculated caches
    through their actual dependencies and recompute them when needed, keeping
    public reads current. Check insertion, deletion, movement, retargeting,
    cloning and bulk-edit behavior so caches cannot silently become stale.
  - Keep stored facts, ordering, identities, connectivity, version gates,
    precision and diagnostic behavior correct. Measure memory costs as well as
    elapsed time; speed changes must preserve meaningful conversion results.

- [x] Write the object-access and model reference alongside the schema work.
  - Establish a clear documentation hierarchy. The primary user guide should
    provide a short path through reading, inspecting/editing and writing a design,
    with optional configuration and reports introduced when useful. Keep the
    model reference organized for lookup rather than requiring a full read.
  - Retain `FORMAT_CAPABILITIES.txt`, `MODEL_CONTRACT.txt` and the existing detailed
    documents as supporting technical/internal references. They are not the
    primary user-facing documentation. Link relevant detail from the guide and
    reference without duplicating it or requiring users to study adapter internals.
  - Begin with a brief, authoritative access-rules section: named bracket reads
    and writes, equivalent `get`/`set`, defaults, `None`, presence checks, optional
    field deletion, required-field constraints and errors for invalid operations.
    Explain that missing bracket reads/deletions raise `KeyError`, `get` returns
    its default for any missing name, and present `None` is distinct from absence.
    Keep child navigation and schema reflection clear, and prefer bracket syntax
    in examples. Use a compact table and a few small examples; avoid showing every
    equivalent spelling or repeating the same examples across documents.
  - Describe the document hierarchy and every supported record and field:
    meanings, types, tuple members, units, coordinate and angle conventions,
    enums, defaults, optional values, cardinality and absent versus empty.
  - Explain identities, reference roles and scopes, unresolved references,
    collection ordering, ownership, authored facts and calculated data.
  - Document named reads and writes, queries, construction, cloning, moving,
    deletion, retargeting, automatic consistency and explicit validation, with
    small examples and their effects on references. Explain any remaining
    advanced rebuilding/projection operation and when it is relevant.
  - Distinguish shared infrastructure from schematic-specific meaning. Explain
    how adapters modernize imports and prepare detached export views, while
    keeping file layouts and version gates in their appropriate adapters.
  - Generate field tables from the authoritative schema where practical. Keep
    the architectural contract and format capability register complementary;
    the model reference describes the editable design rather than duplicating
    each file format's specification.

- [x] Audit the general structure before carrying out broad moves.
  - Review library and application boundaries, module responsibilities,
    dependency direction, duplicated helpers and misplaced format assumptions.
  - Review public entry points, tests, examples, documentation, development
    tools, reference inputs, research results and historical material for correct
    placement. Preserve the public repository and private workspace boundary.
  - Inventory callers and dependencies before moving files. Identify obsolete
    implementations and unnecessary forwarding layers; keep historical work
    archived with its related callers and data.
  - Check naming, documentation links, test discovery, package imports and data
    resource loading. Record the proposed moves and their reasons, then verify
    callers and navigation after each migration step.

- [x] Restructure `lib/` for shared infrastructure and document domains.
  - Establish sibling `common/`, `schematic/` and future `pcb/` areas. Shared tree,
    field-schema infrastructure, queries, reference machinery, diagnostics,
    physical-unit utilities and general geometry belong in `common/` when they
    are independent of the document domain.
  - Give `schematic/` some internal structure: model/schema and constructors,
    format adapters, data-editing helpers, and layout/calculated geometry.
    Group each adapter's reader, writer and version handling together.
  - Keep schematic-specific reference rules, simulator behavior, sheet concepts
    and quarter-turn restrictions with schematic. PCB will own its document
    schema, layers, routing and pour semantics while using shared infrastructure.
    Review genuinely reusable symbol, footprint and text facilities as their
    consumers become clear; shared ownership must not depend on schematic.
  - Keep all schematic formats on one schematic model, with future PCB formats
    using one PCB model built on the same common infrastructure. Dispatch must
    distinguish document kind as well as serialization format as support grows.
  - Preserve the stable `lib` entry point during the transition. Separate
    module moves from behavior changes and update internal imports and callers
    deliberately. Introduce PCB implementation when work on that domain starts;
    the planned directory does not imply existing PCB support.
  - Keep tests with the package they exercise and retain cross-package API tests
    separately. Update test discovery and documented commands as folders move.

Current repository organization:

```text
lib/
  __init__.py                     # Public API and document dispatch
  common/                         # Generic infrastructure and package tests
  schematic/
    model/
    formats/{dch,asc,dchxml}/
    editing/
    layout/
    tests/
  pcb/                            # Reserved future domain
  tests/                          # Facade and integration tests
  deprecated/                     # Earlier attempts and their callers
examples/{schematic,pcb}/
apps/{dch_to_asc,diptrace_bom,diptrace_db}/
references/                       # Detailed supporting/AI reference material
doc/{MODEL,GETTING_STARTED}.md     # Primary user guides
README.md
```

The repository is library-first. Applications and examples consume the same
`lib` entry point. Detailed references supplement the short user guides.

## Current behavior and further work

- Named bracket/get/set/in/del access and immutable schema reflection cover
  supported schematic records. Names are stored once; positional headers are
  adapter projections. The generated MODEL_REFERENCE.md and schematic_schema()
  catalogue describe supported fields, tuple members and ownership for lookup.
  Label groups, user-field headers, table/title records, border/bounds groups,
  drawing points, text rows, sizes and net-class headers now use named storage.
  Redundant grid-position data and self-index bindings for derived indices have
  been removed. Local/global suffix choices refresh bound text immediately.
- Resolved pin/net membership now has one ordered identity owner, with an editable
  reverse Pin.Net view and calculated numeric occurrences. Ordinary assignments
  and retargets keep both views current and reject wire contradictions atomically.
  Unresolved or conflicting imports remain explicit. Existing-field edits now
  activate newly meaningful links, including controller-dependent nested sources.
  Document.copy and Document.remove provide linked-subtree lifecycle operations.
  Mode guards and transitive property-copy dependencies now validate atomically,
  including unresolved guards and derived bound text. Root field overrides during
  copying must agree with managed links. Registered links protect insertions, moves,
  reorders and removals before mutation; affected indices and property chains
  update immediately. Owned links are removed collectively; external users require
  explicit disposal or retargeting. Cross-boundary projection fields require
  explicit relationship editing rather than partial implicit copies.
  Calculated relationship users and guards now follow binding, retargeting and
  discard; whole-document clone builds topology before evaluating dependencies.
  Virtual named fields and collection-size calculations join the same planner.
  Watch snapshots release safely removed subtrees instead of retaining them.
- Simulator argument rows now have real named storage owned by the model, with
  direct DCH/XML decoding and adapter-generated arrays. Hole headers, library
  paths, calculated slot/variant positions and the typed Verification vector are
  declared. The browsable catalogue is generated from the immutable definitions.
- Named definitions now cover wire/bus rows and X/Y/Dir points, classification
  rows/catalog keys, project paths, model text lines, global user-label choices,
  paste segments, internal pad links, differential pairs and pad terminals.
  Classification inputs normalize to CategoryType; terminal counts/positions
  derive from current children. Zone border sizes accept fractional lengths.
  Drawing definitions now distinguish symbol, sheet and footprint contexts.
  Obsolete generated fields are excluded from editable component, drawing and
  pad definitions; absent format-specific settings are optional. A three-input
  metadata audit now finds no missing required or invalid present typed fields.
  Ownership declarations include groups, bus numbers, supplier data, 3D placement
  and typed unresolved keys. Unspecified enum meanings/units remain unspecified.
  Document viewport and nominal identification fields are named; optional
  ActiveSheet follows page identity and supplies the default XML selection.
- Immutable child definitions now describe owned record types and cardinalities;
  explicit full-model audit checks declared child constraints. Counted arrays
  for classifications, possible names, paste segments, project paths and cache
  links no longer keep a redundant count in the normal model. Cache-prefix
  limits remain distinct. Linked copying and owned-link removal use the same
  targeted planner, with external-user protection.
  Targeted structural plans cover ancestor indices, calculated
  ordinal dependents, segment adjacency, keys, unresolved scopes and declared
  cardinalities. Adapter assembly and detached export preparation use explicit
  internal boundaries rather than authoring hooks on incomplete structures.
- validate() audits without projecting indices; advanced rebuild() also projects
  compatibility indices. Scalar/key/property/bound-text edits use targeted
  updates, with private field, reference and identity lookup caches.
- Common ExportContext and destination additions align optional choices and
  independent resolved defaults. serialize() supplies bytes for every format,
  with the same options as file output. Reused reports attribute diagnostics to
  operation, format, file and optional caller label; they are not success logs.
- A concise library guide and object-access/model reference now lead the docs.
  The existing detailed technical documents remain supporting references.
- The common current schematic model and DCH/ASC/DCHXML adapters are implemented
  under design/MODEL_CONTRACT.txt. Import modernizes; detached export adapts.
  Complete imports use current properties and scoped references, without source
  replay or preservation-only snapshots. Portable tests cover editing, natural
  round trips and repeated-conversion stability.
- Segment-local branch normalization supports longer hosts and coherent pin
  anchors, near-corner retargeting, outside projections and dependent short
  branches. Keep pins fixed and joins on their declared segments. Longer/cyclic
  constraints and unknown compatibility directions retain source data and warn.
- Extend the XML mapping for public variants beyond the supported vocabulary.
  XML automatic marking definitions cannot retain individual appearance overrides
  in the supported readers; conversion warns and retains the authoring data.
  Field-bound authored symbol text refreshes independently of placement/style.
  See design/FORMAT_CAPABILITIES.txt
  for exact adapter limits and conversion consequences.
- Keep capability rules and diagnostics current as adapters expand. Companion
  discovery is outside the single-design-file input boundary. ConversionReport
  spans import and export with shared info/warning/error severities.
- Add coordinated connection editing above the data model.
- Add PCB, component-library and pattern-library adapters.
