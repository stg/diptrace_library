# DipTrace Library

DipTrace saves designs as binary files. To use their contents in scripts or
external tools, you normally have to open DipTrace and export them to ASC or XML
first. Without DipTrace, you're stuck. I built this library so you can read, edit
and write those files directly, without that export step or DipTrace installed.

For example, convert a schematic to XML and save an older binary version from
the same design:

```python
design = read("design.dch")
write(design, "design.dchxml", version=52)
write(design, "older.dch", version=46)
```

Now, binary designs can also finally participate in Git tracking, with useful
diffs. The [Git companion app](apps/diptrace_git/README.md) manages text
companions and rebuilds the binary files, so you can review changes in Git and
GitHub without manual exports from DipTrace.

Existing XML-based tools can use the conversion layer to prepare their input and
save their edited results back to the required format. That removes the manual
XML export/edit/re-import steps. Scripts that edit through the shared model also
have their references updated automatically.

I also use it for tasks I would otherwise do manually inside DipTrace, such as
[generating BOMs from schematics](apps/diptrace_bom/README.md) or
[finding where I have used a component before](apps/diptrace_db/README.md).
Scripts can use the same model without each needing its own file parser.
Ordinary use does not require DipTrace to be installed.

## Background

I have spent hundreds of hours digging into DipTrace files over well over ten
years. I've been using DipTrace since before ASC and DCHXML were available as
public export formats, and the collection behind it now spans nearly fifteen years
of my professional and personal work with DipTrace. Much of that time went into
inspecting files, making controlled edits in DipTrace, comparing what changed and
trying different ways of
representing the data. My background in low-level file-format engineering has been
very useful, but DipTrace-files are very complex and while I've been able to solve
quite a lot of problems on a one-by-one basis, a fully-featured solution has always
remained well out of reach. Manual ASC, and recently XML, conversion has become the
go-to solution for programmatic editing and complex operations not natively
supported by DipTrace, but the manual conversion steps have remained a nuisance -
especially for version control!

More recently, I have used agentic workflows to collect and automate reference
conversions, analyze the data, refactor the implementation and expand the
regression checks. The result is a library that finally opens up DipTrace files
to scripts and tools. You can read, edit and write the design data directly,
without manual exports or having to decode the binary formats yourself.
Earlier exploratory attempts are preserved as [deprecated history](lib/deprecated/README.md);
they show some prior approaches that led up to this working implementation.
My collection of hand-written tests, notes and scattered one-off experiments with
the binary formats will **not** be made public :D

## Schematics

Schematic support is the strongest and most extensively checked part of the
library. DCH, ASC and DCHXML all read into the same searchable, editable model,
and all three can be written. Any supported input can therefore be converted to
any supported output, including a different supported file version.

| Format | Input | Output |
| --- | --- | --- |
| Binary schematic (`.dch`) | Schemas 29–52 | Schemas 46–52; default 46 |
| ASCII schematic (`.asc`) | Schematic dialect 46 | Schematic dialect 46 |
| XML schematic (`.dchxml`) | Recognized schematic XML fields[^1] | Schema targets 46–52; default 46 |

Sadly, I have not maintained a schema-to-DipTrace version list over the years.
The schema numbers above are internal file-format revisions. The following
save-format checkpoints are known:

| DCH schema | DIP schema | Verified DipTrace version |
| --- | --- | --- |
| 46 | 54 | 4.3.0.5 |
| 48 | 58 | 4.9.5.0 (beta) |
| 51 | 60 | 5.2.0.1 |
| 52 | 62 | 5.3.5.1 |

All schematic schemas within the listed ranges are supported, including those
between the release checkpoints above. Older versions outside these ranges are
not supported because their behavior has not been verified.

[^1]: XML input coverage extends up to DipTrace 5.3.5.1. See the
    [capability register](references/FORMAT_CAPABILITIES.txt) for field-specific limits.

### Regenerated binaries

A binary regenerated from a text companion should represent the same design,
but may not be identical byte for byte. Writers regenerate bookkeeping, and small
rounding or text-layout differences can also change the bytes without changing
the design's meaning. These conversions are designed to remain stable when
repeated, rather than accumulating positional or numerical drift. There are
also a small number of proven bugs and inconsistencies in DipTrace that are
intentionally not reproduced.

Byte differences alone therefore do not mean that a file is damaged or that
authored data was lost. Conversion reports distinguish routine reconstruction
from meaningful loss and invalid data. The
[capability register](references/FORMAT_CAPABILITIES.txt) documents the limits.

### Editing

You can inspect components, pins, nets, drawings, tables and library definitions;
query named fields; edit values and settings; and copy, move or remove records.

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

The library updates supported older file representations when reading them.
Saving to an older format may leave out data that it cannot represent
(see: [format capabilities](references/FORMAT_CAPABILITIES.txt)). That data remains
in the design you're editing.

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

I check the library against DipTrace by converting files, making controlled edits
and reopening the results. Much of this started as manual comparison work and is
now automated.

The private reference corpus contains:

| Corpus | Size |
| --- | --- |
| Unique source files | 2,572 |
| Source files plus ASCII and XML exports | 7,716 |
| Total disk space | 53.4 GB |
| Schematics (schema 28–48) | 560 |
| PCB layouts (schema 31–58) | 714 |
| Source timestamps | 2011–2026 |

The schematic readers have been checked against the original schematics and
their XML companions. Automated checks include 20 end-to-end writer/reopen
fixtures and 648 portable library tests covering model behavior, adapters and
edge cases.

These files remain private because they contain professional, client, and personal
projects and library collections.

## Accuracy and responsibility

I put a lot of effort into correctness and testing, but I cannot guarantee that
every file, edit or conversion will be handled correctly. Keep backups of your
originals and check the results before relying on them. You are responsible for
deciding whether the library is suitable for your work and verifying the files
you produce with it. The library is provided without warranty; see the
[license](LICENSE) for the full terms.

## Requirements

Tested with **CPython 3.12.3 on Windows**. The active library and applications
use only the Python standard library; no third-party Python packages are needed.
The Git companion also requires Git installed and available on `PATH`.

## Things that use the library

The [applications](apps/README.md) are deliberately basic. They are useful tools,
but show only a small part of what the library can do:

- **[Git companion](apps/diptrace_git/README.md):** track readable design data and rebuild binary working files.
- **[Component usage database](apps/diptrace_db/README.md):** find where a component has been used across projects.
- **[BOM generator](apps/diptrace_bom/README.md):** group components and their reference designators into a CSV.
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
copies of DipTrace.

Contributions to high-level editing tools are welcome too. These belong in a
toolkit alongside the core data library, using its model and editing API to
implement operations such as moving components with their wires or calculating
copper fills.

Contributions may include AI-generated code, however I expect contributors to
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
