# PCB examples

Run these examples from the repository root:

```sh
python -m examples.pcb.create example.dip
python -m examples.pcb.edit example.dip edited.dip
python -m examples.pcb.convert edited.dip edited.dipxml
```

The same examples accept PCB ASC and DIPXML. The create example supplies its
trace geometry explicitly. The edit example demonstrates queries, RefDes
allocation, named fields, user data and reference maintenance after reordering.
Conversion accepts an optional output version and shares one diagnostic report
across input and output.

See the [model guide](../../doc/MODEL.md) for editing boundaries, the
[API reference](../../doc/API.md) for shared operations, and the
[PCB catalogue](../../doc/PCB.md) for records and fields.
