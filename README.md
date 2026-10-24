# DipTrace Library

I built this library to automate work directly on DipTrace design files from
Python. I wanted scripts to read and write the source formats I already use,
and to edit designs without maintaining every related field by hand. Supported
binary, ASCII and XML formats use the same editable model, which coordinates
tracked references and dependent data as changes are made.

Binary designs can now also participate in text-based version control. The
[Git companion app](apps/diptrace_git/README.md) sets up text companions and binary
reconstruction for supported designs, giving Git and GitHub readable diffs and
a reviewable history without manual exports from DipTrace.

For example, convert a schematic to XML and save an older binary version from
the same design:

```python
design = read("design.dch")
write(design, "design.dchxml", version=52)
write(design, "older.dch", version=46)
```

Existing XML-based tools can use the conversion layer to prepare their input and
save their edited results back to the required format. That removes the manual
XML export/edit/re-import steps. Scripts that edit through the shared model also
get automatic reference coordination.

I also use it for tasks I would otherwise do manually inside DipTrace, such as
[generating BOMs from schematics](apps/diptrace_bom/README.md) or
[finding where I have used a component before](apps/diptrace_db/README.md).
Those scripts can share one understanding of the design instead of each needing
its own partial file parser. Ordinary use does not require DipTrace to be installed.

## Background

I have spent hundreds of hours digging into DipTrace files over well over ten
years. I started before DipTrace provided ASC and DCHXML as public export formats,
and the collection behind it now spans nearly fifteen years of my professional and
personal work with DipTrace. Much of that time went into inspecting files, making
controlled edits in DipTrace, comparing what changed and trying different ways of
representing the data. My background in low-level file-format engineering has been
very useful, but DipTrace-files are very complex and while I've been able to solve
quite a lot of problems on a one-by-one basis, a fully-featured solution has always
remained well out of reach. Manual ASC, and recently XML, conversion has become the
go-to solution for programmatic editing and complex operations not natively
supported by DipTrace, but the manual conversion steps have remained a nuisance -
especially for version control!

More recently, I have used agentic workflows to collect and automate reference
conversions, analyze the data, refactor the implementation and expand the
regression checks. The result brings that accumulated work into a library I can
use and extend, rather than a collection of scripts tied to individual projects.
Earlier exploratory attempts are preserved as [deprecated history](lib/deprecated/README.md);
they show some prior approaches that led up to this working implementation. The
larger collection of smaller hand-written tests, notes and one-offs are not
public.

## Schematics

Schematic support is the strongest and most extensively checked part of the
library. DCH, ASC and DCHXML all read into the same searchable, editable model,
and all three can be written. Any supported input can therefore be converted to
any supported output, including a different supported file version.

| Format | Input | Output |
| --- | --- | --- |
| Binary schematic (`.dch`) | Schemas 29–52 | Schemas 46–52; default 46 |
| ASCII schematic (`.asc`) | Schematic dialect 46 | Schematic dialect 46 |
| XML schematic (`.dchxml`) | Recognized 4.3, 4.9, 5.2 and 5.3 vocabulary | 4.3, 4.9, 5.2 and 5.3 vocabulary |

Sadly, I have not maintained a schema-to-DipTrace version list over the years.
The schema numbers above are internal file-format revisions. The following
save-format checkpoints are known:

| DCH schema | Verified DipTrace version |
| --- | --- |
| 46 | 4.3.0.5 |
| 48 | 4.9.5.0 (beta) |
| 51 | 5.2.0.1 |
| 52 | 5.3.5.1 |

Intermediate and earlier release mappings are incomplete. I do not support
older versions outside the listed ranges because I do not own the older
DipTrace versions needed to verify their behavior reliably.

### Regenerated binaries

A binary regenerated from a text companion should represent the same design,
but may not be identical byte for byte. Writers regenerate bookkeeping, and small
rounding or text-layout differences can also change the bytes without changing
the design's meaning. These conversions are designed to remain stable when
repeated, rather than accumulating positional or numerical drift. There are
also a small number of proven bugs and inconsistencies in DipTrace that are
intentionally not reproduced.

Byte differences alone therefore do not mean that a file is damaged or that
authored data was lost. Meaningful format limitations are a separate matter:
conversion reports identify them, and the
[capability register](references/FORMAT_CAPABILITIES.txt) describes them.

### Editing

You can inspect components, pins, nets, drawings, tables and library definitions;
query named fields; edit values and settings; copy, move or remove records; and
work with identity-based relationships.

```python
part = design.one('/Schematic/Components/Part[RefDes="R1"]')
part["Value"] = "22k"
```

The model coordinates supported references automatically. Renaming a component
updates its bound labels and dependent references; reordering records keeps links
attached to the same objects. Edits that would break tracked relationships are
rejected before they are applied, and ordinary editing needs no manual rebuild.

```python
part["RefDes"] = "R12"          # Bound labels and tracked references update.
part.move_to(part.parent, 0)    # Links follow the component's new position in the list.
```

Imports bring supported older representations into the current model. Exports
adapt a separate output view, so choosing an older version does not remove facts
from the design you are editing. Conversion reports distinguish routine
reconstruction from meaningful loss and invalid data. The
[capability register](references/FORMAT_CAPABILITIES.txt) documents the limits.

These are data edits. High-level operations are not implemented: moving a
component does not make its wires follow, changing a library reference does not
import or replace the referenced content, and changing a copper pour's shape
does not calculate its fill. This is not a replacement for DipTrace; it is a
tool for programmatic DipTrace data editing with wide format support.

```python
part["X"] += 30  # Move 10 mm; connected wire geometry stays in place.
```

## PCB layouts

Unpublished, experimental, and not ready for use.

## Components

Unpublished, experimental, and not ready for use.

## Patterns

Unpublished, experimental, and not ready for use.

## Validation

I check behavior by using installed, licensed DipTrace software to convert files
between formats, make controlled edits, reopen the results and observe what
changes. A lot of this comparison work was originally manual; the repeatable
checks are now automated as canonical conversions. The private reference corpus
contains **2,572 unique accepted source files**, each with independently checked ASCII and XML exports:
**7,716 files and 53.4 GB** in total.

That includes **560 schematics and 714 PCB layouts** from professional and
personal projects, with source timestamps spanning **2011–2026**.

The schematic binary reader has been checked against all 560 original
schematics: 558 are within its supported range, and two older files are explicitly
rejected. All 560 canonical XML companions have also been imported. Generated
checks include 20 end-to-end writer/reopen fixtures, alongside 599 portable
library tests covering model behavior, adapters and edge cases.

I keep these files private because they contain company and personal property,
including projects and associated library collections. They provide repeatable
comparisons against DipTrace's own
load/save behavior; the family sections above describe the library's tested scope.

## Accuracy and responsibility

I put a lot of effort into correctness and testing, but I cannot guarantee that
every file, edit or conversion will be handled correctly. Keep backups of your
originals and check the results before relying on them. You are responsible for
deciding whether the library is suitable for your work and verifying the designs
you produce with it. The library is provided without warranty; see the
[license](LICENSE) for the full terms.

## Requirements

Tested with **CPython 3.12.3 on Windows**. The active library and applications
use only the Python standard library; no third-party Python packages are needed.
The Git companion also requires Git installed and available on `PATH`.

## Things that use the library

The [applications](apps/README.md) are deliberately basic. They are useful tools,
but show only a small part of what the library can do:

- **Git companion:** track readable design data and rebuild binary working files.
- **Component usage database:** find where a component has been used across projects.
- **BOM generator:** group components and their reference designators into a CSV.
- **[Format converter](apps/diptrace_convert/README.md):** convert between formats or output versions.

The [three schematic examples](examples/schematic/README.md) cover creation,
inspection/editing and conversion. For your own scripts, start with
[Getting started](doc/GETTING_STARTED.md) and [the model guide](doc/MODEL.md).
The [API reference](doc/API.md) covers the supported operations with focused examples;
the [schematic catalogue](doc/SCHEMATIC.md) lists every declared record and field.

## Bugs and contributions

If a supported file fails to load, converts incorrectly or loses meaningful data,
please [open an issue](https://github.com/stg/diptrace_library/issues) and include
a file that reproduces it, the DipTrace version and the operation you attempted.
Only attach files you are comfortable sharing publicly; a small reproducer is welcome.

I would particularly welcome contributions from active DipTrace users who want
to extend format or version support and can check the results with their own
installed, licensed copies of DipTrace.

Contributions to high-level editing tools are welcome too. These belong in a
toolkit alongside the core data library, using its model and editing API to
implement operations such as moving components with their wires or calculating
copper fills.

Contributions are welcome, including AI-generated code. I expect contributors to
understand and review what they submit, hold it to a high standard, and include
a strong set of relevant tests. Only submit a pull request if you can personally
explain, verify and stand behind the work.

To run the self-contained checks from the repository root:

```sh
python -m unittest discover -s lib -t .
python -m unittest discover -s apps -t .
```

## License

This project is licensed under the [MIT License](LICENSE). Included Unicode data
retains its [Unicode license](lib/common/text/LICENSE.unicode.txt).
