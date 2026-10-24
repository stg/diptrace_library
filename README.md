# DipTrace schematic tools

The editable design library imports DCH, ASC and DCHXML into one searchable
schematic model. It supports data inspection, scalar and tuple edits, record
insertion, cloning, moving, reordering and reference rebuilding.

- [Library API](lib/design/README.txt)
- [Library development list](lib/TODO.md)
- [Format capabilities and conversion rules](lib/design/FORMAT_CAPABILITIES.txt)
- [DCH to ASC command](dch_to_asc/README.md)

DCH input supports schemas 29 through 52. DCH output supports 46 through 52;
ASC output uses schematic dialect 46. XML adapters cover recognized public
fields, with explicit limits documented in the capability register.
Select output version 52 for fractional fonts, monospacing and current XML fields.

Routine reconstruction produces quiet informational notices; meaningful losses
and unresolved input constraints produce warnings. ConversionReport collects
import and export notices with the same info/warning/error severities. Unknown
mappings and invalid input/output remain errors. Export
preparation operates on a detached view of the model.

The component database and BOM commands use the shared model:

```sh
python diptrace_db/build_db.py --root inputs --out component_db.json
python diptrace_bom/build_bom.py input.dch output.csv
```

Earlier decoder experiments and their callers are preserved under `deprecated/`.
They are separate from the current library and application entry points.

Routing, coordinated connection editing and copper-pour calculation are future
layers. PCB, component-library and pattern-library file adapters are future work.

Run the self-contained library tests from this directory:

```sh
python -m unittest discover -s lib/design/tests
```
