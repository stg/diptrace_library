# Schematic BOM

```sh
python diptrace_bom/build_bom.py input.dch output.csv
```

Groups components by name, value and pattern, with their reference designators.
The same command accepts ASC and DCHXML inputs through the shared model. Only
enabled physical components are included; repeated RefDes values contribute once.
Run with `--help` for command options.
