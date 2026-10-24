# Getting started

This guide takes a schematic through a small read, inspect, edit and save
workflow. You can start with a binary DCH file or an ASC/DCHXML export; the
editing code is the same for all three.

If you want a command-line converter rather than a Python API, use the
[format converter](../apps/diptrace_convert/README.md).

## Before you begin

See [requirements](../README.md#requirements) for the tested Python environment
and tool dependencies.

Run Python from the repository directory containing `lib/`. The examples below
use a file named `design.dch` and build on one another in a single session.

Use your own schematic, or create the small example design from the repository:

```sh
python -m examples.schematic.create design.dch
```

That example contains a connector named `J1`, a pin, a net and a drawing.
With your own file, replace the filename and component reference as you go.

## Open the design

```python
from lib import read, write

design = read("design.dch")
```

`read()` chooses the input format from the extension and returns a `Document`.
The document holds the editable design in memory. Reading does not change the
input file, and edits stay in memory until you write them.

You can use `design.asc` or `design.dchxml` here instead. You do not need to
export a binary schematic from DipTrace before using the library.

## See what is in it

A document contains records organized into collections. For example,
`/Schematic/Components` contains the placed components. List their reference
designators, names and values:

```python
parts = design.select("/Schematic/Components/Part")
for part in parts:
    print(part["RefDes"], part["Name"], part["Value"])
```

`select()` returns a list of matching records. The records are the actual
objects in the design, so editing one changes the document.

Use `one()` when you expect exactly one match:

```python
part = design.one('/Schematic/Components/Part[RefDes="J1"]')
```

If your file has no `J1`, choose a reference from the list you just printed.
`one()` raises `LookupError` if there is no match or more than one; it will
not silently select the first of several multipart units.

The [schematic catalogue](SCHEMATIC.md) lists the available collections and
fields. The [model guide](MODEL.md) explains how records fit together.

## Make an edit

Fields are read and written with brackets:

```python
part["Value"] = "Sensor input"
print(part["Value"])
```

For an optional field, `get()` lets you provide a fallback:

```python
print(part.get("Datasheet", "No datasheet supplied"))
```

Assignments check the field's type and relationships before changing it.
Supported references and dependent text stay coordinated automatically; you do
not need to call a rebuild method after editing.

These are data edits. Changing a component's position does not make its wires
follow it, and changing a library filename does not load a new definition.
The [editing boundary](MODEL.md#data-editing-and-geometry) explains that distinction.

## Save or convert it

Write a new binary file, or choose another extension to convert the design:

```python
write(design, "edited.dch")
write(design, "edited.dchxml")
```

Both files come from the same in-memory design. The original `design.dch` stays
untouched. Writers use the documented default output version unless you select
one; they do not automatically reuse the input version. If compatibility with a
particular DipTrace release matters, see the [support table](../README.md#schematics)
and [version selection](API.md#versions).

## Work with related records

Navigation goes beyond searching for whole components. A component owns its
pin collection, and a pin can refer to a net:

```python
pins = part.child("Pins").children("Pin")
for pin in pins:
    net = pin["Net"]
    print(pin["StringNumber"], net["Name"] if net is not None else "Unconnected")
```

Here `child()` navigates to one owned record or collection, while `children()`
lists its contents. `pin["Net"]` follows a relationship to another record.
Assignments to supported relationship fields also maintain the corresponding
data elsewhere in the design. See [relationships](API.md#relationships) for
connection editing, and [searching](API.md#searching) for filtering by field values.

## Review conversion notices

An output format may not carry every fact in the design. To inspect conversion
notices in your script, attach a report:

```python
from lib import ConversionReport

report = ConversionReport()
write(design, "checked.dchxml", report=report)
for notice in report.warnings:
    print(notice.rule, notice.message)
```

Information notices describe routine normalization or reconstructable output.
Warnings describe meaningful loss or uncertainty. Invalid operations still raise
exceptions, whether or not a report is attached.

You can pass the same report to `read()` and several writes to collect a whole
job's diagnostics. Call `report.clear()` before starting a fresh collection.
Without a report, warnings use Python's normal warning mechanism.
The [report reference](API.md#reports) describes notice fields and severity rules.

## Override output settings when needed

Ordinary conversion uses the design's stored settings and standard defaults.
An optional context changes choices for one output without changing the design:

```python
from lib import ExportContext

write(
    design,
    "in_mils.dchxml",
    context=ExportContext(units="mil"),
)
```

This changes the output's unit representation; it does not rescale your stored
coordinates. See [configuration](API.md#configuration) for other overrides,
effective defaults and font measurement.

## Where to go next

| If you want to… | Read |
| --- | --- |
| Understand ownership, identities and automatic consistency | [The model guide](MODEL.md) |
| Look up a function, method, parameter or exception | [The API reference](API.md) |
| Find a schematic record, field, type or unit | [The schematic catalogue](SCHEMATIC.md) |
| Start from a complete script | [Creation, editing and conversion examples](../examples/schematic/README.md) |
| Have a look at functional applications | [Applications](../apps/README.md) |

The API reference also covers [bulk filtering](API.md#searching),
[RefDes matching and allocation](API.md#reference-designators),
[copying and removal](API.md#construction-and-ownership), and
[working with byte buffers](API.md#reading-and-writing).
