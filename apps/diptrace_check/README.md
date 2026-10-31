# Check a design's round trips

`diptrace_check` saves and reopens one design several times, comparing the named
model data and reference targets after each pass. I use it as a quick way to
spot conversion problems without running a corpus test.

```sh
python -m apps.diptrace_check design.dch
python -m apps.diptrace_check design.dch --format dchxml --json check.json
python -m apps.diptrace_check design.dch --format dch --format asc --format dchxml
```

The input is detected from its content and is never overwritten. By default the
check exercises that same format using the library's default output version.
`--format` selects another serialization; it can be repeated. `--version` selects
an exact supported output schema when checking one format. No generated design
files are saved: each round trip happens in memory.

The command uses the same family-neutral library API for schematics, PCB layouts,
components and patterns. It becomes available for each family as its adapters are
published. An unavailable family or version produces the library's normal error;
the command does not enable experimental adapters.

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

Exit codes are `0` for clean/rounding, `1` for review/drift or a processing failure,
and `2` for invalid command arguments. `--json` records counters, example changes
and conversion notices. `--report-level` filters the usual console diagnostics.

This is a diagnostic, not a proof that a design is correct. It checks the current
model through the library's own writers and readers, without opening DipTrace.
It does not compare rendered text, calculate routing or pours, or establish
physical equivalence after a change in local coordinate frames. Difficult cases
still need inspection, and a stable conversion can share a bug in both adapters.
