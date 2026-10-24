# DipTrace schematic applications

These applications use the shared [design library](../README.md) to convert
schematics, find prior component usage and build bills of materials.

## Why these exist

The original need was to quickly answer:
"Where have I already used this component so I can source compatible spare parts
for new designs?"

Because DipTrace `.dch` files are binary, normal text search does not work well.
The component database makes prior usage searchable across projects. The same
library also supports BOM extraction and schematic conversion.

Run the following commands from the repository root.

## Component usage database

`diptrace_db` recursively scans DCH files and groups component usage by name,
value and pattern. It supports incremental rebuilds and produces JSON for
component lookup and BOM reuse.

```sh
python -m apps.diptrace_db.build_db --root inputs --out component_db.json
```

A typical entry includes the component signature and its design locations:

```json
{
  "name": "Resistor",
  "value": "150",
  "pattern": "RES_0603_N",
  "files": ["ProjectA/PowerSupply.dch", "ProjectB/ControlBoard.dch"]
}
```

See [database options](diptrace_db/README.md).

## Schematic BOM

`diptrace_bom` groups enabled physical components by name, value and pattern,
with naturally sorted reference designators. It accepts DCH, ASC and DCHXML.

```sh
python -m apps.diptrace_bom.build_bom input.dch output.csv
```

See [BOM options](diptrace_bom/README.md).

## DCH to ASC

`dch_to_asc` converts a supported binary schematic to ASC, with optional context
for export choices and font measurement.

```sh
python -m apps.dch_to_asc.convert input.dch output.asc
```

See [conversion options](dch_to_asc/README.md). Each command also accepts `--help`.
