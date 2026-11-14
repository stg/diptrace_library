# Check a design's round trips

Use `diptrace_check` to see how the library handles your own designs before
relying on its conversions, and to find cases that need better support. It saves
and reopens one design several times, comparing named model data and reference
targets after each pass. DipTrace is not required.

```sh
python -m apps.diptrace_check design.dch
python -m apps.diptrace_check design.dch --format dchxml --json check.json
python -m apps.diptrace_check design.dch --format dch --format asc --format dchxml
```

The input is detected from its content and is never overwritten. By default the
check exercises that same format using the library's default output version.
`--format` selects another serialization; it can be repeated. `--version` selects
an exact supported output schema or application release when checking one
format. No generated design
files are saved: each round trip happens in memory.

The same command checks schematics, PCB layouts, component libraries and pattern
libraries through the common library API. Format and version support comes from
the [library's capability tables](../../README.md), with no separate app limits.
An unavailable family or version produces the library's normal error.

```sh
python -m apps.diptrace_check parts.eli --format elixml --version 5.3.5.1
```

## Compare with DipTrace exports

Supply the original design and ASC/XML files exported from that **same saved
revision** in DipTrace:

```sh
python -m apps.diptrace_check board.dip --reference board.asc --reference board.dipxml --json check.json
```

`--reference` can be repeated. Contents identify each reference's family and
format, regardless of its filename. The app adds those formats to the checks,
matches their declared output versions and display units, and compares the first
library output with each reference. It also runs the usual stability checks.
All supplied files stay untouched. The app never launches or automates DipTrace;
you provide the exports.

Each reference has two comparisons:

- **model** compares imported data and reference targets in the editable model.
- **serialized** compares the ASC/XML records and values directly, including
  content the editable model might miss. It ignores indentation, XML attribute
  order, comments and equivalent numeric spelling; content order remains visible.

These results are separate from round-trip changes. A documented omission can
change data when switching formats while still agreeing with DipTrace's export
of that format. An outdated reference can also produce differences; a mismatch
does not by itself establish a library bug. If a reference cannot be imported
into the model, its direct comparison and import error remain in the report.

Version matching uses the library's declarations, with no automatic fallback to
another XML release. Where several schema targets share a header version, the
highest matching target is selected and all candidates are recorded. Use
`--format` with `--version` to select another matching target when checking a
single format. Multiple references can exercise different supported versions.

## What the checks establish

Round-trip checks test the library's own consistency. Matching DipTrace exports
adds an external reference for the design data that those formats contain. Both
are useful evidence; neither establishes the correctness of every omitted or
reconstructed fact. The limits below still apply.

## Reading the result

- **clean**: the checked facts agree exactly.
- **rounding**: the first save makes only small numerical changes, and subsequent
  saves remain stable.
- **review**: the first round trip changes text, flags, references, field presence
  or numbers beyond the selected threshold. Check the JSON examples and conversion
  notices; a documented format adaptation can explain a difference.
- **drift**: later saves keep changing the first output beyond the stability
  threshold. This includes further normalization that needs investigation, even
  if it eventually settles.

The default initial numerical threshold is `0.0005` in each field's **model
unit**. This is not a universal physical distance: a shared length unit is one
third of a millimetre, while angles and other quantities have their own units.
Integer settings, text and reference targets always compare exactly. See the
[model guide](../../doc/MODEL.md) for units and data ownership.

Later saves compare against the **first** output, using the much smaller default
`--drift-tolerance 1e-9`. Many individually small steps therefore cannot disappear
inside the initial rounding allowance. Use `--tolerance`, `--drift-tolerance` and
`--cycles` to investigate a particular case; at least two cycles are required,
and the default is three. Zero tolerances request exact numerical comparisons.

Direct reference comparisons use exact numerical values by default.
`--reference-tolerance` allows small differences in each value's **serialized
units**, independently of the model threshold. Those units can differ between
fields and exports; they are not a single physical distance. Whole-integer
changes, text and record structure remain exact. All measured differences are
reported even when within tolerance.

Exit codes are `0` for clean/rounding, `1` for review/drift or a processing failure,
and `2` for invalid command arguments. A reference mismatch also returns `1`.
`--json` records counters, example changes and conversion notices, with reference
comparisons under each result's `references` list. `--report-level` filters the
usual console diagnostics.

This is a diagnostic, not a proof that a design is correct. Without supplied
references, it checks only the library's own writers and readers. Even with
references, interpreting formats and identifying fields still uses library code.
It does not compare rendered text, calculate routing or pours, or establish
physical equivalence after a change in local coordinate frames. Difficult cases
still need inspection, and a stable conversion can share a bug in both adapters.

If a result is unexpected, check the reported changes and conversion notices.
A documented adaptation can explain a difference; a repeatable unexplained change
is useful evidence for a [bug report](../../README.md#bugs-and-contributions).
Include the command, JSON report, DipTrace version and a small reproducing design
you can share publicly. Import or conversion failures are worth reporting too,
even when the command cannot finish producing a JSON report. Review reports for
private paths and design content before sharing them.
