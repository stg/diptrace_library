# Library development

## Next: examples and model usability

- [ ] Provide common runnable examples under `apps/examples/`, using small,
  self-contained public designs. Cover:
  - Reading DCH, ASC and DCHXML into the common model; inspecting components,
    pins, nets, fields and references.
  - Searching and bulk editing component values and user fields.
  - Cloning, moving and reordering records, retargeting references and rebuilding.
  - Creating a small schematic and adding drawing data.
  - Converting between the three formats, choosing output versions, supplying
    optional context and reviewing import/export reports.
  Keep examples focused on data editing and verify their observable results with
  portable checks. Higher-level editing remains deferred; examples may mention
  future coordinated connection editing, trace following or pour calculation
  when explaining the current scope.
  - Record friction found while writing or using each example as actionable
    improvement items in this list: awkward queries, missing named access,
    repetitive construction, unclear units, reference handling, diagnostics or
    documentation gaps. Include the triggering task and desired behavior.
  - Prefer generic improvements to the model, API or documentation that benefit
    other callers. Avoid solving friction only inside an example with ad hoc
    helpers. Distinguish current data-editing gaps from deferred higher-level
    operations; recording an item does not bring those operations into scope.

- [ ] Define and document a model with named fields and a consistent editing API.
  - Give every meaningful field a declared name, including values currently
    accessed as positional arguments. Public ASC/DCHXML vocabulary guides names;
    neither format's serialized layout defines the shared model.
  - Use `get(name, default=None)` and `set(name, value)` for ordinary field access.
    `get` returns a declared field's current value, or the supplied default when
    that field is absent. Reject unknown field names and invalid assignments
    promptly. Keep child navigation and record queries separate from field reads.
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

Proposed field access after this work (not the current API):

```python
part = document.one('//Part[RefDes="R1"]')
part.get("RefDes")
part.get("Datasheet", "")
part.set("RefDes", "R12")
part.set("Value", "22k")
pins = part.child("Pins")
```

- [ ] Align the public reading, writing, reporting and configuration APIs.
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

- [ ] Make model coherence automatic during ordinary data editing.
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

- [ ] Audit and improve speed across the model, readers and writers.
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

- [ ] Write a complete model reference alongside the schema work.
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

- [ ] Audit the general structure before carrying out broad moves.
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

- [ ] Restructure `lib/design/` for shared infrastructure and document domains.
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
  - Preserve the stable `lib.design` entry point during the transition. Separate
    module moves from behavior changes and update internal imports and callers
    deliberately. Introduce PCB implementation when work on that domain starts;
    the planned directory does not imply existing PCB support.
  - Keep tests with the package they exercise and retain cross-package API tests
    separately. Update test discovery and documented commands as folders move.

Proposed organization, to refine during the structure audit:

```text
apps/
  examples/
  lib/
    design/
      __init__.py                 # Public entry point and document dispatch
      common/
        model.py                  # Generic tree and typed values
        schema.py                 # Field/record definition infrastructure
        query.py
        references.py             # Generic identity and reference machinery
        conversion.py             # Reports and diagnostic contracts
        geometry.py
        units.py
        text/                     # Shared measurement services and metrics
        tests/
      schematic/
        model/                    # Named schema, defaults, constructors, links
        formats/
          dch/
          asc/
          dchxml/
        editing/                  # Existing data-editing helpers
        layout/                   # Markings and calculated geometry
        tests/
      pcb/                        # Future PCB domain and adapters
      tests/                      # Public API and cross-package integration
```

Use this as an ownership plan, adding subpackages where responsibilities justify
them. Sequence the work so that the audit and model definitions guide the moves,
the examples exercise the new API, and format behavior remains verified.

## Current behavior and further work

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
