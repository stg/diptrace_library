# DipTrace library applications

These are small tools built with the [design library](../README.md): keep text
companions in Git, convert formats, find prior component usage and build bills
of materials. You can also check how the library handles your own designs.
These tools show a few uses of the library rather than its full API.

## Designs in Git

`diptrace_git` maintains generated ASC/XML artifacts for ordinary Git commands
and rebuilds native working files from checked-out revisions. Unchanged text
leaves the original binary untouched.

```sh
python -m apps.diptrace_git --repo /path/to/project init
```

The [Git companion guide](diptrace_git/README.md) covers setup, enable/disable
pathspecs, ownership, hooks and day-to-day use.

## Format and version conversion

`diptrace_convert` recognizes designs and library definitions, chooses the output
format from its extension and can select an output version. It works with all
four document families. See
[conversion options](diptrace_convert/README.md).

```sh
python -m apps.diptrace_convert input.dch output.dchxml
python -m apps.diptrace_convert input.dchxml output.dch --version 52
```

## Check the library with your designs

`diptrace_check` compares data and references across repeated save/reopen cycles,
separating initial rounding from larger changes or accumulating drift. Supply
matching DipTrace ASC/XML exports with `--reference` to compare against those
too. Your originals stay untouched; the app does not run DipTrace. Use it to
assess the library with your own designs and find cases that need better support.

```sh
python -m apps.diptrace_check design.dip --json check.json
```

If a check fails or something looks wrong, please
[open an issue](../README.md#bugs-and-contributions) with the command, JSON report
and a design you can share. The [check app guide](diptrace_check/README.md)
explains the different checks and how to read the results.

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
| 1 | Processing failed, a batch skipped files, or a check needs review |
| 2 | Invalid arguments or configuration |

Git's own command output and exit status pass through when `git diptrace commit`
runs Git. `selection` prints the ordered pathspec decisions without message prefixes.
Application helpers live in `apps/common`; the library itself does not print
terminal progress or choose an application's output policy.
