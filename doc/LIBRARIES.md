# Component and pattern libraries

A pattern library contains reusable physical footprints. A component library
contains logical components: their descriptions, one or more symbol parts, and
an optional physical pattern. These are definitions, rather than components
placed in a schematic or PCB. They have no placed net membership or routed
traces.

Each family's binary, ASC and XML files use the same editable model. The common
[API](API.md) covers reading, queries, fields, relationships, copying and writing.
The generated [pattern](PATTERN.md) and [component](COMPONENT.md) catalogues list
every record and field. Consult the README support tables or
`format_capabilities()` for supported versions.

## Read, inspect and convert

```python
from lib import read, write

library = read("parts.lib")
for pattern in library.select("/Library/Patterns/Pattern"):
    print(pattern["Name"], len(pattern.select("Pads/Pad")))
write(library, "parts.libxml")
```

Inputs are identified by content. An exported XML file does not need a special
filename extension to import. Outputs use the supplied extension or explicit
`format`; ASC output belongs to the current document's family.

A component's symbols and physical pattern occupy different branches:

```text
/Library
  Categories
  Subfolders
  Components
    Component
      Parts
        Part
          Pins / Pin
          Shapes / Shape
          Groups / pt
      Pattern                    optional physical definition
        Pads / Pad
        Shapes / Shape
        Holes / Hole
        Dimensions / Dimension
      UserFields / UserField
      Suppliers
```

Pattern libraries instead use `/Library/Patterns/Pattern`, with the same
physical children. Paths use ownership names; the catalogue's record type names
identify schemas. For example, a symbol drawing is still found through
`Shapes/Shape` even though its schema distinguishes it from a physical drawing.

## Edit the current definition

Use named fields and the ordinary query API:

```python
component = library.one("/Library/Components/Component[1]")
component["Manufacturer"] = "Example Devices"
for part in component.select("Parts/Part"):
    for pin in part.select("Pins/Pin", where=lambda pin: pin["Name"] == "ENABLE"):
        pin["Name"] = "EN"
```

Descriptions such as Name, RefDes, Manufacturer and Datasheet belong to the
component. Access through a part refers to that same value; it does not create
an independent copy. Part-specific values, symbol geometry and simulation
settings remain with the part.

A component's RefDes is a library default, not an allocation of a placed
reference designator. Library entries are not subject to placed-design
RefDes uniqueness rules.

Physical pad labels and symbol pin labels are also separate facts. A pin's
`Pad` selects a physical pad by identity; `StringNumber` is the authored label
on the symbol. Assigning one does not silently overwrite the other:

```python
pin = component.one("Parts/Part[1]/Pins/Pin[1]")
pad = component.one("Pattern/Pads/Pad[2]")
pin["Pad"] = pad
pin["StringNumber"] = "A2"
```

Reordering the pads keeps the selection attached to that pad and updates its
serialized index. Removing a selected target is rejected until its references
are cleared or retargeted. As elsewhere in the model, invalid edits are atomic.

Library folders, categories, classification types and subtypes use managed
identities. Prefer selecting the target record to setting a key and label
separately. Renaming a selected definition updates its projections. Unresolved
or conflicting imported selections remain explicit; a similarly named entry is
not chosen by guesswork. Physical classifications inside an attached component
pattern have their own scope.

## Construct a small library

```python
from lib.pattern import new_library, new_pattern, new_pad
from lib import write

library = new_library("Example footprints")
pattern = library.one("/Library/Patterns").append(new_pattern("Two pads"))
for number, x in (("1", -1.5), ("2", 1.5)):
    pad = pattern.one("Pads").append(new_pad(number, x=x))
    pad["SurfacePad"] = True
    pad["PadShape_New"] = 2
    pad["PadWidth_New"] = 1.8
    pad["PadHeight_New"] = 2.4
write(library, "example.libxml")
```

The common model uses three shared length units per millimetre. The example
therefore places pad centres 1 mm apart, with 0.6 mm by 0.8 mm pads. Use
`library.in_units("mm")` for a view with natural physical units; see
[measurement views](API.md#measurement-views). Angle domains remain specific
to their records: physical pad, drawing and 3D angles must not be interpreted
as schematic quarter-turn placement values.

Imports normalize the local symbol and footprint frames, adjusting their
origins along with the geometry. Raw coordinates can therefore differ from
another serialization while describing the same definition. These local
coordinates are separate from a component's eventual placement in a design.

Constructors supply editable records and initial defaults. Attaching a record
establishes its types and relationships immediately. Collection `.add()` is
also available for declared records; see the API's
[construction rules](API.md#construction-and-ownership).

## Derived values and authoring settings

Group membership is meaningful data. Group indices and centres follow the
current members and geometry; imported stale centres are not saved as another
source of truth. Text measurements can affect a group's calculated envelope.
Text uses `FontWidth` for its stroke; geometric drawings use `Width`. Inactive
serialization slots do not create a second text stroke in the model.
Output uses the chosen destination's text conventions, with an optional
`ExportContext.text_layout` override when a font measurement service is needed.

Default pad settings, verification choices, template parameters, recovery
settings and model attachments are retained as data. Editing template
parameters does not regenerate pad or drawing geometry. Changing the attached
pattern does not infer new pin-to-pad assignments. A 3D filename or library
reference does not cause another file to be opened. These operations require
an application or an additional editing algorithm.

## Output choices and diagnostics

Contexts are optional. The standalone families share the same ImportContext and
ExportContext types. ImportContext selects the code page for narrow binary
strings. ExportContext can select XML units, a default drawing stroke,
text-layout services and ASC receiver conventions. ASC byte encoding is an I/O
option; XML output is UTF-8.

```python
from lib import ConversionReport, write
from lib.pattern import ExportContext

report = ConversionReport()
write(library, "parts.libxml", context=ExportContext(units="mm"), report=report)
for notice in report.notices:
    print(notice.severity, notice.message)
```

Export adapts a detached view and leaves the source model unchanged. Some
destinations omit information or normalize calculated values. Expected
reconstruction is information; meaningful irreversible loss is a warning;
invalid or unimplemented output is an error. A report collects diagnostics
without suppressing failures. See [reports](API.md#reports) and the capability
register for individual conversion rules.
