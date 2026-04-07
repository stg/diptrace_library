# DipTrace Schematic Decoding

Decode DipTrace binary schematic files (`.dch`) and build a searchable component usage database.

## Why This Exists

Main focus: I needed to quickly answer:
"Where have I already used this component so I can source compatible spare parts for new designs?"

Because DipTrace `.dch` files are binary, normal text search does not work well.  
This repo solves that by decoding `.dch` data and indexing prior component usage across projects.

It already decodes substantially more than component usage from `.dch` files. While not yet a complete DipTrace decoder, it is a practical base for custom tooling and deeper exploration of the DipTrace `.dch` format.

Feel free to contribute any findings that may help improve the decoder.

## Apps

### `diptrace_db`

`diptrace_db` scans workspace, builds JSON database from unique signatures:
- `name`
- `value`
- `pattern`

### Features

- Recursive scan of workspace for DipTrace `.dch` files
- Incremental rebuild support for fast re-runs
- Search-ready JSON output for component lookup and BOM reuse
- Shared `.dch` decoder library for future apps

### Run

```sh
python diptrace_db/build_db.py --root /path/to/workspace --out component_db.json
```

### Input / Output

- Input: DipTrace schematic binaries (`.dch`)
- Output: JSON database mapping unique `(name, value, pattern)` to file usage locations

### Example Output (trimmed)

```json
{
  "name": "",
  "value": "150",
  "pattern": "RES_0603_N",
  "files": [
    "ProjectA/PowerSupply_R3.dch",
    "ProjectB/ControlBoard_R12.dch"
  ]
}
```

### `diptrace_bom`

Builds a BOM CSV from one `.dch` input.

Groups by unique `(Name, Value, Pattern)` and outputs:
- `RefDes` list
- `Name`
- `Value`
- `Pattern`

Run:

```sh
python diptrace_bom/build_bom.py input.dch output.csv
```

### `dch_to_asc`

Early development skeleton for structural `.dch` -> `.asc` work.

Status:
- Not a functional end-user app yet
- Used as a development scaffold for decoder parity and future ASC generation
- Output is intentionally partial/incomplete

Run:

```sh
python dch_to_asc/build_asc.py input.dch output.asc
```

## `lib/` (shared decoding library)

`lib/` contains shared DipTrace `.dch` decoder code used by this app and future apps in this repository.
