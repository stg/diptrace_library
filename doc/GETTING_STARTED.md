# Getting started

Read DCH, ASC or DCHXML into one editable model, then write any supported
format. Run Python from the repository directory containing `lib/`.

```python
from lib import ConversionReport, read, write

report = ConversionReport()
design = read("design.dch", report=report)
part = design.one('/Schematic/Components/Part[RefDes="R1"]')
part["Value"] = "22k"
write(design, "edited.dch", version=52, report=report)

for notice in report.warnings:
    print(notice.message)
```

Use `select(path)` for multiple matches and `one(path)` when exactly one is
expected. Navigate collections with `child()` or paths; read and edit fields
with brackets. [The model guide](MODEL.md) describes
defaults, deletion, relationships and reflection.

`parse(data, format="dch")` imports an in-memory buffer;
`serialize(design, format="dch")` exports bytes with the same options as `write()`.
Input consumes the supplied file; it does not discover companions.

Configuration is optional. Stored settings take precedence over standard
defaults (mm display units, vector text, font size 2); explicit export context
overrides affect only the output view. Imports modernize supported old data;
exports adapt a detached view without changing the design.
`ExportContext` provides common overrides for all formats; specialized
`DchExportContext`, `AscExportContext` and `DchXmlExportContext` add destination
options. Construct defaults directly, inspect `.resolved(design, format="dch")`
on a common context, and customize
with `dataclasses.replace`. `ImportContext` configures legacy binary modernization.

One `ConversionReport` can collect notices from multiple reads and writes.
Notices include the operation, format and filename; buffer operations can use
an optional `label="..."`. Reports contain diagnostics, not a log of clean successes.
Information describes equivalent normalization or reconstructable omissions;
warnings describe unresolved constraints or meaningful loss. Errors still raise
exceptions. Without a report, warnings use Python's warning mechanism.

DCH input supports schemas 29–52; output supports 46–52, defaulting to 46.
ASC uses schematic dialect 46. DCHXML supports the recognized public schematic
vocabulary. These examples cover data inspection and editing; high-level editing,
such as automatic routing, is a separate layer. See the
[family status sections](../README.md#schematics) for current support.

For detailed limits and advanced options, see the supporting
[model catalogue](../references/MODEL_REFERENCE.md), [API notes](../references/API_NOTES.txt),
[capability register](../references/FORMAT_CAPABILITIES.txt) and [model contract](../references/MODEL_CONTRACT.txt).
The [three runnable examples](../examples/schematic/README.md) cover creation, editing and conversion.
