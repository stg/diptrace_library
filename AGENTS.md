# DipTrace library

Build a reusable library for reading, inspecting, searching, editing, converting
and writing DipTrace design data. Its scope is schematics, PCB layouts,
components and patterns. `lib/` owns the library; `apps/` contains its consumers.

## Scope and boundaries

Schematics are currently supported. Other document families are unpublished,
experimental and not ready for use. Do not remove a family's ignore rules or
start tracking its implementation until the user explicitly confirms stability.
Keep existing public placeholder files tracked. State capabilities and maturity
separately for each family.

This Git repository contains portable code, tests, examples and documentation.
Keep development utilities, reference designs, research material and private
validation runners in the surrounding workspace, outside the repository.

## Layout

- `lib/__init__.py` is the public entry point.
- `lib/common/` owns generic tree, schema, query, reference, reporting, RefDes,
  geometry and text infrastructure. It must not import document domains or
  format adapters. RefDes rules are shared across schematic and PCB models.
- `lib/schematic/` owns `model/`, `formats/{dch,asc,dchxml}/`, `editing/`
  and `layout/`. Shared destination policy belongs under `formats/`.
- `lib/pcb/` reserves the PCB domain. Add other family packages when ready to
  publish; their schemas, adapters and domain rules stay with those packages.
- `lib/deprecated/` archives earlier attempts with their callers. They are not
  active backends or fallback readers.
- `apps/` contains applications. Shared CLI reporting, file checks and component
  selection belong in `apps/common/`; adapter/version policy stays in `lib/`.
- Tests belong with their package/application. `lib/tests/` owns public API and
  integration tests; `lib/common/tests/` and `lib/schematic/tests/` own package tests.
- `examples/<family>/` contains a small, focused set of runnable workflows.

Move callers and resources with implementations. Do not retain forwarding trees
or duplicate active implementations solely for old imports.

## Documentation

Human-facing Markdown belongs in `doc/`:

- `GETTING_STARTED.md` provides a progressive read/inspect/edit/write workflow,
  introducing further detail when useful and linking to reference material.
- `API.md` is a lookup reference: signatures, arguments, results, constraints
  and focused independent examples.
- `MODEL.md` separates shared model concepts from document-family overviews.
- `SCHEMATIC.md` is the single field/ownership catalogue, generated from the
  same schema definitions used by the model.

These documents must cover the supported public API/model without requiring
implementation notes. Keep examples executable. Link to the support table and
version query rather than repeating version ranges throughout the guides.

Plain `.txt` implementation/AI material belongs in `references/`. Maintain the
model contract and capability register as behavior changes. `DEVELOPMENT.txt`
is a development record, not an active checklist or a second source of rules.
Link to the generated catalogue rather than maintaining another copy.

## Model and conversion rules

Follow [MODEL_CONTRACT.txt](references/MODEL_CONTRACT.txt) and maintain
[FORMAT_CAPABILITIES.txt](references/FORMAT_CAPABILITIES.txt).

All serializations of a family use its same searchable, editable current model.
Use public ASCII/XML vocabulary for field names where applicable. Keep one
authoritative representation per meaningful fact, identity and ordering.
Derive redundant indices and reverse views. Missing optional/calculated data
is absent, without duplicate availability flags.

Import modernizes supported older representations; export adapts a detached view.
Do not retain source bytes, obsolete snapshots or contradictory historical values
for reconstruction. Diagnostic metadata must not choose writers, grant output
eligibility or control binding. Import consumes one supplied file without
companion discovery. Explicit syntax inspection is separate from normal editing.

Named and structural edits preflight affected constraints and maintain references,
keys and bound text incrementally. Invalid edits must be atomic. Ordinary edits
and saves require no manual rebuild. Private indexes/caches are implementation
state, not authored or serialized facts. Literal text remains independent of
calculated labels.

Contexts are optional overrides. Schematic fallbacks are mm, vector text and font
size 2, with stored settings taking precedence. Keep capability queries and
adapters on the same version declarations. Report equivalent normalization and
reconstructable omissions as info, meaningful loss or unresolved constraints as
warnings, and invalid/unimplemented operations as errors. Errors still raise.

The library provides data editing. Routing, wire following, pour calculation and
other high-level editing algorithms are a separate layer. Keep angle rules with
their family: schematic export normalizes/rounds to quarter turns; footprint and
3D angle domains remain separate.

## Independent implementation and observable evidence

Independently design our code, algorithms, data structures and measurement data.
Derive interoperability rules and necessary numerical metrics from ordinary
design files and observable application behavior, including controlled edits and
canonical conversions using installed, licensed DipTrace software.

Every included interoperability rule, format constant or measurement must have
a concrete external derivation: explain how files, conversions, fixtures or
calculations can produce it. Merely asserting that something could be measured
is insufficient. Describe evidence accurately; a proposed measurement is not a
performed experiment.

Use our own representations for published format facts and measurement datasets.
Include only facts and numerical values needed for interoperability whose
derivation can be demonstrated through design files and observable conversions.
File-format constants and measurable results may naturally agree; correctness
does not require making them different. Apply this rule across all document
families and measurements, including font/layout metrics.

Prefer general verified rules. A corpus mismatch alone does not justify an
exception. Do not invent filename, fixture, version or arbitrary-threshold
heuristics. Bounded layout/rounding differences are acceptable when meaning and
repeated-conversion stability hold. Do not reproduce incidental application bugs
solely to recover byte identity.

Keep private designs, local reference filenames, machine-specific paths and
private development material outside the repository. Apply the same publication
boundary to deprecated material. Public explanations must stand on observable
files and behavior without requiring private inputs.

## Verification

From the repository root:

```sh
python -m unittest discover -s lib -t .
python -m unittest discover -s apps -t .
```

Run checks appropriate to the change. Keep portable fixtures self-contained;
private saved-reference checks belong outside the repository. Use normal Python
bytecode caching; `.gitignore` excludes caches and compiled files.
