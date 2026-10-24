# DCH to ASC

Convert a supported DCH schematic to schematic ASC dialect 46:

```sh
python -m apps.dch_to_asc.convert input.dch output.asc
```

Export uses stored settings and standard defaults. Add
`--context apps/dch_to_asc/context.example.json` to override display units, project
directory, font choices or fallback line widths. `--windows-fonts` enables the optional Windows font measurement
provider for system-font text. Vector layout is self-contained.

Input schemas 29 through 52 are supported. Known omissions warn; unknown versions,
unsupported mappings and missing required resources fail explicitly. Export
preparation uses a detached model and finishes before writing the output file.

Run from the repository root. The converter uses the editable
[design library](../../doc/GETTING_STARTED.md).
