# DipTrace designs in Git

DipTrace normally saves binary designs. This companion keeps readable ASC or XML
representations in Git and leaves native files available for DipTrace. Changes
can be reviewed on GitHub or with ordinary Git tools, without manual exports.

## Which files belong to the tool

For a schematic, the files are:

| File | Purpose |
| --- | --- |
| `design.dch` | Native working design; ignored by Git |
| `design.dch.git.xml` | Generated XML representation; tracked |
| `design.dch.git.json` | Reconstruction settings, including native version; tracked |

With ASC selected, the text file is `design.dch.git.asc` instead. There is one
text companion per design. Keeping the full native filename distinguishes files
from different DipTrace modules. The final extension still identifies the actual
content, including in a downloaded source archive.

XML companions use `.xml` for every module. The native extension earlier in the
name identifies the family, so the app selects that family's XML adapter
explicitly. The library recognizes input content; output adapter selection remains explicit.

Files named `design.asc` or `design.dchxml` belong to you. The tool does not manage
them. The `.git.*` names identify its artifacts and avoid taking over your own
exports. These files remain writable; ownership does not depend on local file
permissions. Their diffs also remain visible on GitHub.

Edit the native design in DipTrace or through the library. The text and JSON
companions are generated, tool-owned artifacts, not another working copy of the
design. They exist for review, exchange and reconstruction through Git. Allowing
both copies to be edited independently would make it unclear which design to keep.

## Setup and selection

Run this once from the library checkout, supplying your project's Git directory:

```sh
python -m apps.diptrace_git --repo /path/to/project init
```

Then, from that project:

```sh
git diptrace enable '*.dch'
git add --all
git commit -m "Track schematics as text"
```

XML is the default. Use `init --text-format asc` for new ASC companions. Existing
pairs retain the format recorded by their artifact filenames. Keep the library
checkout and its Python environment available; rerun `init` if they move.

Selection uses Git pathspecs, evaluated against native filenames relative to the
repository root. A group can include Git's exclusion magic:

```sh
git diptrace enable ':(glob)**/*.dch' ':(exclude)archive/**'
git diptrace disable 'prototype/**'
git diptrace enable ':(top,literal)prototype/approved.dch'
git diptrace selection
```

Enable/disable operations are applied in order; later decisions override earlier
ones. Quote patterns so the shell leaves them for Git. These are pathspecs, not
`.gitignore` patterns: use `disable` or `:(exclude)`, rather than `!archive/**`.
Literal, glob, top and case-insensitive magic are available; attribute-based
pathspecs are not supported for virtual native filenames.
Use explicit magic in stored rules; ambient Git pathspec environment switches
do not change the repository's selection.

The app maintains an exact ignore list for selected native files and filter
attributes for its `.git.*` artifacts. Disabling a design keeps its files and
stops managing them. Its native file may then appear as untracked. Selection
settings are committed in `.diptrace-git.json`; executable paths, hooks and the
cache stay in local Git metadata. Stage managed ignore/attribute changes along
with the configuration and artifacts.

If native files are already tracked, use `enable --untrack '*.dch'`, or
`sync --untrack --stage` after selecting them. This removes native files from the
index while preserving local files and existing history.

Schematics (`.dch`) and PCB layouts (`.dip`) are supported with ASC or XML
artifacts. Use `enable '*.dip'` to select layouts. Dispatch is also prepared for
component (`.eli`) and pattern (`.lib`) libraries; those adapters remain
unavailable. Unsupported families and reconstruction versions produce library
errors. See the [schematic](../../README.md#schematics) and
[PCB](../../README.md#pcb-layouts) support tables.

### After cloning

Run `init` in each clone to install the local integration. It retains committed
settings and detects the initial direction from the files present:

- A native file without companions is exported, preserving the original.
- Tracked companions without a native file are rebuilt in the recorded version.
  This is the usual first setup after cloning.
- When both exist without a local baseline, the tool verifies that the pair
  agrees before adopting it. A missing cache does not authorize replacement of
  an existing native file. A mismatch requires an explicit direction.

Repeated setup leaves matching designs and artifacts untouched. Unsupported
versions are errors. `init --fallback-earlier` explicitly permits an earlier
writable native version, with a warning. Version support comes from the library;
see the [schematic](../../README.md#schematics) and
[PCB support tables](../../README.md#pcb-layouts), and
[format capabilities](../../references/FORMAT_CAPABILITIES.txt).

### Existing installations

The earlier companion layout and selection configuration require an explicit
migration:

```sh
git diptrace init --migrate
```

Without a local alias yet, invoke the Python module as in the first setup command.

Migration moves only artifacts identified by the old reconstruction metadata,
updates their names and settings, and keeps native files unchanged. It refuses
edited legacy artifacts or an occupied destination. Ordinary user exports with
no ownership record are left alone. Review and commit the resulting Git changes.
Existing history is not rewritten; an old revision using the earlier layout
needs migration before this version can manage it.

Legacy ignore patterns are converted to the existing selected filenames, rather
than guessed at as pathspecs. Use `enable` afterward to choose patterns that should
also include future designs.

## Everyday use

Edit and save the native design, then use ordinary Git commands:

```sh
git status
git diff
git add --all
git commit -m "Update the design"
```

For already tracked artifacts, `git commit -am "Update the design"` also notices
native-only edits. New designs still need `git add`, as ordinary new files do.
The old `git diptrace commit` command remains as a compatibility wrapper; it is
not required for everyday commits.

`sync`, `export`, `rebuild` and `check` accept selected native or artifact paths
relative to the repository root. `check` previews without writing designs;
`--verify` checks content even if cached file metadata matches. `--stage` stages
only generated artifacts and refuses to replace an existing staged snapshot.

## How synchronization works

Git tracks the generated artifacts and ignores the native working file. The tool
compares cached file metadata and content hashes to determine what changed.
An unchanged companion leaves the native file's bytes and timestamps untouched.
Timestamp-only and line-ending-only changes do not cause a native rebuild.
Removing the cache requires verification, not permission to replace an original.

A meaningful native edit causes a new text export. The tool writes that export
only when its contents differ. Git still controls staging: generated files are
not a reason to replace a partially staged snapshot or include an unrelated design
in a commit. Ordinary `git add` and `git commit -am` are the intended daily flow.

The unusual part is how Git notices a change to an ignored native file. Git can
otherwise reuse its cached result for an unchanged text companion and never run
a content filter. A custom `core.fsmonitor` hook refreshes the selected artifacts
before Git examines working files. This uses a documented extension point for a
purpose beyond its usual filesystem-change reporting role.

Reconstruction uses the text and settings actually present in the working tree.
`post-checkout`, `post-merge`, `post-rewrite` and `post-index-change` hooks reconcile
Git's updates. The monitor also checks actual files on subsequent Git operations.
Content filters do not rebuild a native file from their input: Git can invoke
smudge simply to show a historical object, without checking it out.

A monitor error cannot veto a Git command. The integration therefore records the
failure, invalidates the affected text's cached stat information and uses a
required clean filter to reject stale staging. Pre-commit validation supplies an
additional check. Post-operation hook errors cannot undo a Git update; they must
report that native synchronization is incomplete while preserving existing data.

These are separate responsibilities, not a transactional guarantee supplied by
Git. The cache and the hooks must remain idempotent because one command can invoke
several of them. Brief overlapping queries wait for the same synchronization;
Git's own index-lock failures remain ordinary retry conditions.

## Errors and recovery

An unexpected manual change to a generated text companion is reported instead of
silently replacing the native design. To discard it and regenerate from the native
file, review the affected design and run:

```sh
git diptrace export design.dch --force --stage
```

To keep the edited text instead, explicitly accept it as replacement design data:

```sh
git diptrace rebuild design.dch --force
```

The latter replaces the local native file. Review the result before committing.
Forced conversions require explicit paths so a decision about one design cannot
rewrite every native file in the repository.
The same export command can recreate a missing companion or reconstruction JSON.
Removing both artifacts deliberately leaves the local native file alone; select
it again with `enable` to enroll it as a new pair.

An unresolved text merge keeps the last valid native file. Resolve the Git
conflict first; do not treat that native file as the merged result. Rebuilding
validates the resulting text through the library, but structural validity cannot
establish that a merge expresses the contributors' intentions. Review the design.

Use `git apply --index` when applying patches to managed artifacts: the index
update gives the integration a confirmed Git revision to import. Plain
`git apply` only edits working files and has no general after-apply hook. Such a
change is treated like another direct artifact edit and requires explicit
acceptance rather than silently changing the native design.

Invalid inputs, conflicting independent changes, unavailable conversions and
files changed during conversion produce errors. Keep the files, resolve the
reported cause and retry. A conversion failure is not a reason to use an older
cached export as if it represented the current native design. A selected invalid
design blocks synchronization; disable it if work on other designs must continue.

A regenerated binary can differ in bytes while representing the same design.
See [regenerated binaries](../../README.md#regenerated-binaries) for normalization
and conversion limits. An unresolved merge or failed reconstruction leaves the
last native file in place; it must not be mistaken for the new Git revision.

## Assumptions and compatibility

The integration depends on Git running the configured monitor, filters and hooks.
A client which implements Git operations itself and bypasses them is outside the
supported workflow. Explicitly disabling hooks or filters also disables their
protection. Do not replace another configured filesystem monitor without an
explicit compatibility decision.

Git 2.26 or newer is required for monitor protocol 2. The workflow tests have
been exercised with Git 2.29.0.windows.1 and schematic fixtures in ASC and XML.
PCB regressions cover export, native-edit commits and checkout in both formats.
That does not establish every Git version, client, filesystem or future adapter.
A GUI using another Git executable must meet the same requirements. Managed
artifacts cannot use `assume-unchanged` or `skip-worktree`; clear those flags or
disable the design instead.

Setup preserves existing hooks, including hooks it does not otherwise use, and
wraps them without editing their programs. It refuses to replace another
configured filesystem monitor or a conflicting filter driver. Choose which
integration to keep before installation.
The local integration settings are shared by linked worktrees, while their
conversion caches are separate. Per-worktree overrides of managed Git settings
must be reconciled before setup; they are not silently replaced or ignored.

`git diptrace uninstall` restores prior local settings and removes only the
managed ignore and attribute blocks. It keeps designs, artifacts, project
configuration and the cache. If a managed Git setting was changed afterward,
uninstall stops rather than overwriting the user's new value.
An interrupted setup can be resumed with `init` or undone with `uninstall`.
Its hooks refuse to process designs while installation is incomplete.

## Why the implementation changed

The [earlier implementation at commit
`13c0320`](https://github.com/stg/diptrace_library/tree/13c03205e4b1d3a9e2fb9e932fdff120d87f56bc/apps/diptrace_git)
used `git diptrace commit` to export and stage companions before calling Git.
That handles a real ordering problem: a pre-commit hook can run too late for
Git's initial decision about whether anything changed. Its checkout, merge and
rewrite hooks also leave some operations needing an explicit sync.

The current integration makes ordinary Git commands notice native edits. It keeps
the useful conversion cache and original-file preservation rules. The trigger
sequence changes; generated companions also have
an explicit ownership rule and names that leave users' exports alone.

I am not a Git expert, and this is an unusual combination of Git features. The
reasons and limits belong in this guide so others can assess them. Suggestions
and contributions that make the integration simpler or more reliable are welcome.

Git references: [hooks](https://git-scm.com/docs/githooks),
[content filters](https://git-scm.com/docs/gitattributes),
[`git cat-file --filters`](https://git-scm.com/docs/git-cat-file), and
[pathspec syntax](https://git-scm.com/docs/gitglossary#Documentation/gitglossary.txt-aiddefpathspecapathspec).

Commands and diagnostic levels follow the [application conventions](../README.md#command-output).
Run any command with `--help` for its options.
