# Component usage database

Find which schematics use a component, identified by its name, value and pattern.
Only enabled physical components with a reference designator are included.
Authored names are preserved.

```sh
python -m apps.diptrace_db.build_db --root path/to/designs
python -m apps.diptrace_db.build_db
```

The first run requires `--root`. Later runs reuse the directory saved in the
database. If it has moved or disappeared, supply another with `--root`; the app
never chooses a scan directory on your behalf. The scan currently covers DCH files.

The default output is `DipTraceLibrary/component_db.json` in your Documents
folder, whose resolved location is printed at startup. This follows the system
Documents location on Windows and Linux, with `~/Documents` as the Linux fallback
and macOS location. Use `--out FILE` on each run to select another database.

## Saved data

The JSON contains component-to-file links, the scan root and file metadata for
reusing those links. Design paths are relative to the saved root:

```json
{
  "version": 2,
  "root": "/path/to/designs",
  "files": {
    "power.dch": {"mtime_ns": 1730000000000000000, "size_bytes": 1234}
  },
  "components": [
    {"name": "Resistor", "value": "10k", "pattern": "R_0603", "files": ["power.dch"]}
  ]
}
```

Unchanged file times and sizes skip import. New or modified files are read;
deleted files disappear. `--clean` rereads everything while keeping the saved
root. Old or malformed caches are rebuilt. `--workers N` enables parallel reading;
one reader is the default.

Bad files are reported, omitted and retried on the next run. Scan counts appear
at completion; diagnostics and run statistics are not saved in the database.
Run from the repository root; `--help` lists options. Diagnostic filtering and
exit codes follow [the application conventions](../README.md#command-output).
