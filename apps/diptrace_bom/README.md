# Schematic BOM

Build a component list for purchasing or further processing:

```sh
python -m apps.diptrace_bom.build_bom input.dch output.csv
```

DCH, ASC and DCHXML inputs use the same component selection as the usage database:
enabled physical components with a reference designator. Repeated RefDes values
count once, using the first occurrence's facts. Parts group by name, value and
pattern; references and rows sort naturally, so R2 precedes R10.

CSV columns are RefDes, Name, Value and Pattern, with UTF-8 text, semicolon
separators and quoted fields. Import and grouping finish before the output is
opened, so a failed import leaves an existing BOM untouched.

Run from the repository root; `--help` lists options. Diagnostic filtering and
exit codes follow [the application conventions](../README.md#command-output).
