# Schematic examples

Run these from the repository root. The first creates a small design; the others
also accept its ASC and DCHXML exports.

```sh
python -m examples.schematic.create example.dch
python -m examples.schematic.edit example.dch edited.dch
python -m examples.schematic.convert edited.dch edited.dchxml --version 52
```

- `create`: components, pins, net membership and drawing points.
- `edit`: named fields, queries, user fields, relationships and record order.
- `convert`: format conversion, optional context and shared diagnostics.

Buffer equivalents are `parse(data, format=...)` and `serialize(design, format=...)`.
See [getting started](../../doc/GETTING_STARTED.md) for a first workflow, or the
[API reference](../../doc/API.md) for operations, options and version selection.
