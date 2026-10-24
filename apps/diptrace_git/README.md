# DipTrace designs in Git

`diptrace_git` keeps readable text companions for DipTrace design files, with
ordinary binary working files for DipTrace. It uses the shared library for
conversion in both directions.

## Why this exists

Binary DipTrace files are awkward to review in Git. Keeping a text export alongside
each design makes changes readable, but manually exporting before every commit
and rebuilding after a checkout is easy to forget.

This tool sets up that workflow in an existing repository. Git tracks a text
companion and a small JSON file; the working binary is ignored. This also makes
collaborative changes easier to review and exchange.

**Current support:** schematic files. PCB layouts, components and patterns are
not yet available; they belong to the same intended workflow as their library
adapters become available. The examples below use the currently supported
schematic formats:

```text
design.dch          working file for DipTrace, ignored
design.dchxml       readable design data, tracked
design.dch.git.json  original binary version and reconstruction instructions, tracked
```

DCHXML is the default. ASC can be selected instead; each design has one text
companion, not both. The JSON explains its purpose and records the original DCH
schema version. It contains no local paths, timestamps or binary checksums.

## Setup

Run this once from the library checkout, supplying your project's Git directory:

```sh
python -m apps.diptrace_git --repo /path/to/project init
```

Then, from your project directory:

```sh
git diptrace rules add '*.dch'
git diptrace rules add '!archive/**'
git diptrace sync --stage
git add .diptrace-git.json .gitignore
git commit -m "Track schematics as text"
```

Rules use Git's ignore-pattern syntax, including exclusions. Positive rules must
end in `.dch` so they cannot accidentally hide unrelated files. For ASC, pass
`--text-format asc` to `init`. That choice applies to new pairs; existing pairs
keep the text format recorded in their JSON.

If DCH files are already tracked, use `git diptrace sync --untrack --stage` for
the initial conversion. This removes the selected binaries from Git's index,
keeping their working files and leaving existing history alone.

Setup installs the local `git diptrace` command and wraps the supported hooks,
calling any previous hook afterward. Existing hook programs are left intact;
unrelated ignore entries are preserved. Run `init` once in each new clone to
install the integration and reconstruct any missing binaries. Keep this library
checkout and its Python environment available; rerun `init` if they move.

## Everyday use

Edit and save in DipTrace, then commit through:

```sh
git diptrace commit -m "Update the schematic"
```

This synchronizes selected designs and stages generated companions before
calling `git commit` with your arguments. Your ordinary staged changes remain
part of that commit. Direct edits to tracked text still use normal Git staging;
the tool does not automatically stage those edits.

A pre-commit hook also handles ordinary commits. When ignored DCH files are the
only changes, however, Git can initially see an empty index and reject the commit
even though the hook has prepared the companions. `git diptrace commit` avoids
that ordering problem. Git GUIs may likewise show no changes until you run
`git diptrace sync --stage`.

Checkout/switch, successful merges and rebases refresh binaries through
`post-checkout`, `post-merge` and `post-rewrite`. Git does not provide those same
hooks for every operation: after commands such as `reset --hard`, `restore`,
`stash pop` or `apply`, run `git diptrace sync` yourself.
See [Git's hook documentation](https://git-scm.com/docs/githooks).

## Keeping local work safe

An unchanged text companion leaves the existing binary untouched. Its first
export establishes a baseline without regenerating the original DCH. Timestamp
or line-ending changes alone do not trigger a rebuild. Missing binaries are
reconstructed from their tracked text and JSON in the recorded version.

The local cache normally lives in `.git/diptrace-git/state.json`. Linked worktrees
have separate caches. Unchanged designs need only metadata checks; checksums
resolve content changes when needed. Removing the cache causes safe revalidation,
not permission to overwrite an existing binary.

If both sides changed independently, synchronization stops for a decision.
`git diptrace check` previews the work. After reviewing the files, choose one
direction for the particular design:

```sh
git diptrace export design.dch --force --stage
git diptrace rebuild design.dch --force
```

Forced conversion requires explicit file paths, so resolving one conflict cannot
rewrite every original in the repository. Synchronization also checks for files
changed during conversion and protects existing staged companion snapshots.
A checkout/pull hook failure does not roll Git back: resolve the reported issue
and rerun `sync`.

Regenerated binaries should contain the same design but may differ in their
bytes. The library's [conversion explanation](../../README.md#regenerated-binaries)
describes normalization, small layout/rounding differences and repeated-conversion
stability. Format limitations are reported separately; conversion warnings remain
visible. A checksum detects a local change, not whether two different binaries
represent equivalent designs.

## Merging and contributions

Readable text makes multi-user review and merging more practical, but Git merges
lines rather than DipTrace objects. One change may update identities and
references in many places. A merge without textual conflicts can therefore still
combine those changes incorrectly. Rebuilding imports the resulting text through
the library's normal checks; those checks cannot establish that a valid merged
design expresses the contributors' intentions.

I am not a Git expert, and there may be a better way to handle this. Remembering
to use `git diptrace commit` adds friction to an otherwise familiar workflow.
I would welcome suggestions and contributions that make working with DipTrace
files feel more like ordinary Git use.

DipTrace-aware merging is not implemented. Contributions are welcome: a merge
tool that understands objects, identities and their related references would be
a useful companion to this workflow. Review merged designs with that distinction
in mind. See the [contribution guidelines](../../README.md#bugs-and-contributions).

## Versions and maintenance

The recorded binary version must be writable by the library. Unsupported exact
versions are errors. `init --fallback-earlier` explicitly permits the best earlier
supported version, with a warning; it never silently upgrades a file. Files that
the library can read but cannot write in their original version therefore cannot
always be managed by this workflow. Version support comes from the library's
`format_capabilities()` query, shared with its adapters.

`sync`, `export`, `rebuild` and `check` accept optional binary or companion paths
relative to the project root. Without paths they consider all selected designs;
`--verify` checks content even when cached file metadata matches.

Use `git diptrace rules list` to view selection rules, or `rules remove PATTERN`
to remove an exact rule. Add an exclusion such as `!/design.dch` to stop managing
one file. Existing companions are kept; removing a rule does not delete files.

`git diptrace uninstall` restores the previous hooks and removes the local alias
and managed ignore block. Designs, text companions, configuration and cache are
kept. The working DCH files may then appear as untracked files again.

Messages and diagnostic filtering follow the [application conventions](../README.md#command-output).
`--report-level info` also shows normalization details from conversions performed
during that run; unchanged pairs are not reimported merely to collect diagnostics.

Every command accepts `--help`. The same commands are available through
`python -m apps.diptrace_git --repo /path/to/project` from the library checkout.
