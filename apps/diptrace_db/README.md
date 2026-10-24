# Component usage database

Scan a supplied directory for DCH files and index component signatures:

```sh
python -m apps.diptrace_db.build_db --root inputs --out component_db.json
```

Run from the repository root, with `--help` for incremental scan and output options.
The shared design reader supplies enabled physical components. Cached results
from older extraction formats are rebuilt. One worker is the default; use
`--workers` to trade memory for parallel parsing.
