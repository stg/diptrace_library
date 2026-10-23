# Component usage database

Scan a supplied directory for DCH files and index component signatures:

```sh
python diptrace_db/build_db.py --root inputs --out component_db.json
```

Run with `--help` for incremental scan and output options.
The shared design reader supplies enabled physical components. Cached results
from older extraction formats are rebuilt. One worker is the default; use
`--workers` to trade memory for parallel parsing.
