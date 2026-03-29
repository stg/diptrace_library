# diptrace_bom

Create a simple BOM CSV from a single DipTrace `.dch` schematic.

Groups components by unique `(Name, Value, Pattern)` and merges matching `RefDes` into a comma-separated list.

Output columns:
- `RefDes`
- `Name`
- `Value`
- `Pattern`

Run:

```powershell
python diptrace_bom/build_bom.py input.dch output.csv
```
