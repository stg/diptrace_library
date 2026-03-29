# diptrace_db

Build a central database of unique `(name, value, pattern)` combinations from all DipTrace `.dch` files.

## Run

```powershell
python apps/diptrace_db/build_db.py --root D:\Sync\ExternalProjects --out analysis\component_combo_db.json
```

Clean rebuild (no input DB cache):

```powershell
python apps/diptrace_db/build_db.py --clean
```

Shared helper modules for this and future apps are in `apps/lib`.
