# DipTrace Library

I built this library to work with DipTrace design files directly from Python:
convert formats and versions, inspect a design, search its contents, make changes
and write it back. I also want to automate things I would normally have to do
manually inside DipTrace, such as generating BOMs from schematics or finding
where I have used a component before. I use it for tasks that would otherwise
mean a lot of clicking or another one-off script with its own partial
understanding of the file.

The library gives those scripts a shared data model and a consistent read/edit/write
API. Supported formats are both inputs and outputs. Ordinary use does not require
DipTrace to be installed.

## Background

I have spent hundreds of hours digging into DipTrace files over well over ten
years. I started before DipTrace provided ASC and DCHXML as
public export formats, and the collection behind it now spans nearly fifteen
years of my professional and personal work with DipTrace. Much of that time went
into inspecting files, making controlled edits in DipTrace, comparing what changed and trying different
ways of representing the data, long before I had AI tools to help with it.

More recently, I have used agentic workflows to collect reference conversions,
analyze the data, refactor the implementation and expand the regression checks.
The result brings that accumulated work into a library I can use and extend,
rather than a collection of scripts tied to individual projects. Earlier
exploratory attempts are preserved as [deprecated history](lib/deprecated/README.md);
they show the approaches that led up to this working implementation.

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

You can inspect components, pins, nets, drawings, tables and library definitions;
query named fields; edit values and settings; copy, move or remove records; and
work with identity-based relationships. Supported edits maintain affected
references and dependent data automatically.

For example, changing a value, converting to XML and saving an older binary
version all use the same design object:

```python
from lib import read, write

design = read("design.dch")
design.one('/Schematic/Components/Part[RefDes="R1"]')["Value"] = "22k"
write(design, "edited.dchxml", version=52)
write(design, "edited.dch", version=46)
```

Imports bring supported older representations into the current model. Exports
adapt a separate output view, so choosing an older version does not remove facts
from the design you are editing. Conversion reports distinguish routine
reconstruction from meaningful loss and invalid data. The
[capability register](references/FORMAT_CAPABILITIES.txt) documents the limits.

The current API covers data inspection and editing. High-level editing, such as
automatic wire following or copper-pour calculation, is a separate layer.

The binary reader has been checked against all 560 original schematics in my
private corpus: 558 are within its supported range, and two older files are
explicitly rejected. All 560 canonical XML companions have also been imported.
Generated checks include 20 end-to-end writer/reopen fixtures, alongside 570
portable library tests covering model behavior, adapters and edge cases.

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
personal projects,
with source timestamps spanning **2011–2026**. Those designs and their text-format
companions account for **6.84 GB**. The rest of the collection contains 633
component libraries and 665 pattern libraries with their exported companions.
Rejected or corrupt inputs are kept out of the reference corpus.

I keep these files private because they contain company and personal property,
including projects and associated library collections. They provide repeatable
comparisons against DipTrace's own
load/save behavior; the family sections above describe the library's tested scope.

## Things that use the library

The [applications](apps/README.md) are deliberately basic. They are useful tools,
but show only a small part of what the library can do:

- **Component usage database:** find where a component has been used across projects.
- **BOM generator:** group components and their reference designators into a CSV.
- **DCH-to-ASC converter:** a small command-line wrapper around the conversion API.

The [three schematic examples](examples/schematic/README.md) cover creation,
inspection/editing and conversion. For your own scripts, start with
[Getting started](doc/GETTING_STARTED.md) and [the model guide](doc/MODEL.md).
Detailed API and model definitions are in [references](references/README.md).

## Bugs and contributions

If a supported file fails to load, converts incorrectly or loses meaningful data,
please [open an issue](https://github.com/stg/diptrace_library/issues) and include
a file that reproduces it, the DipTrace version and the operation you attempted.
Only attach files you are comfortable sharing publicly; a small reproducer is welcome.

I would particularly welcome contributions from active DipTrace users who want
to extend format or version support and can check the results with their own
installed, licensed copies of DipTrace.

To run the self-contained checks from the repository root:

```sh
python -m unittest discover -s lib -t .
python -m unittest discover -s apps -t .
```
