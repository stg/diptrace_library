# DipTrace library applications

These are small tools built with the [design library](../README.md): keep text
companions in Git, convert formats, find prior component usage and build bills
of materials. They show a few uses of the library rather than its full API.

## Why these exist

The original need was to quickly answer:
"Where have I already used this component so I can source compatible spare parts
for new designs?"

Binary designs are difficult to search with ordinary text tools. The component
database makes prior usage searchable across projects. The same library now also
supports format conversion, BOM extraction and readable Git companions.

Run these commands from the repository root.

## Designs in Git

`diptrace_git` keeps tracked text companions and rebuilds working binaries when
those companions change. Unchanged text leaves the original binary untouched.

```sh
python -m apps.diptrace_git --repo /path/to/project init
```

The [Git companion guide](diptrace_git/README.md) covers setup, selection rules,
hooks and day-to-day use.

## Format and version conversion

`diptrace_convert` chooses formats from file extensions and can select an output
version. See [conversion options](diptrace_convert/README.md).

```sh
python -m apps.diptrace_convert input.dch output.dchxml
python -m apps.diptrace_convert input.dchxml output.dch --version 52
```

## Component usage database

`diptrace_db` links components to the designs that use them. The first run needs
a scan directory; subsequent runs reuse it and skip unchanged files.

```sh
python -m apps.diptrace_db.build_db --root inputs
python -m apps.diptrace_db.build_db
```

The default output is in your Documents folder. See [database options and saved
data](diptrace_db/README.md).

## Schematic BOM

`diptrace_bom` groups physical components and their reference designators into a
CSV, accepting the library's supported schematic inputs. See [BOM details](diptrace_bom/README.md).

```sh
python -m apps.diptrace_bom.build_bom input.dch output.csv
```

## Command output

Every command accepts `--help`. Progress and completion use `Info:` on stdout;
diagnostics use `Info:`, `Warning:` or `Error:`, with warnings and errors on
stderr. `--report-level info|warning|error` selects the minimum diagnostic level
(default: warning). Progress stays visible at every level. Normalization details
are available at `info`; warnings alone do not make a command fail.

| Exit code | Meaning |
| --- | --- |
| 0 | Completed successfully |
| 1 | Processing failed, or a batch skipped files |
| 2 | Invalid arguments or configuration |

Git's own command output and exit status pass through when `git diptrace commit`
runs Git. `rules list` prints the selection rules without message prefixes.
Application helpers live in `apps/common`; the library itself does not print
terminal progress or choose an application's output policy.
