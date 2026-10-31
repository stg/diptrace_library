# Working with PCB data

The shared editing concepts are described in [the model guide](MODEL.md);
individual PCB records are listed in the generated [PCB catalogue](PCB.md).

## Read, inspect and write

Binary DIP, PCB ASC and DIPXML all import into the same model. Input recognition
uses the file content; the filename does not need the usual suffix. Output uses
the destination suffix, or an explicit `format` argument.

```python
from lib.pcb import read, write

design = read('board.dip')
write(design, 'board.dipxml')
```

`parse()` accepts an in-memory buffer and `serialize()` returns bytes. Neither
conversion needs DipTrace installed or searches for companion files. Import
modernizes older representations. Export adapts a detached view, keeping the
editable source unchanged. See the main support table for version limits;
`format_capabilities()` reads the same declarations used by the adapters.

```python
from lib.pcb import format_capabilities

support = format_capabilities('dip')
print(support.read_versions, support.write_versions, support.default_write_version)
```

Choose `version=` when a particular output revision is needed. Omitting it uses
the adapter's default, which need not match the input revision. Unsupported
versions raise `UnsupportedFileError`; the library does not silently substitute
another revision.

The generic `lib.read()`, `lib.parse()`, `lib.write()` and `lib.serialize()` use
these same adapters. Choose the PCB family's context classes for PCB operations;
an input filename or diagnostic metadata does not select a different model.

For explicit format investigation, `read_source()` and `parse_source()` expose
the ASC or DIPXML syntax tree. Call `source.as_pcb()` to import a detached editable
model. These source views are separate inspection tools; normal `read()` already
performs that import. Binary source input already returns the PCB model.

## Ownership and queries

The main record is `/Board`. It owns components, nets, layers, rules, drawings,
copper pours and other document settings. Each component owns its current
physical `Pattern`, including pads, holes and footprint drawings. Nets own trace
geometry; a pad's net assignment is a managed relationship. `CacheLib` owns
unplaced library definitions separately from their placed instances.

Queries return the actual editable records:

```python
connector = design.one('/Board/Components/Component[RefDes="J1"]')
pads = connector.select('Pattern/Pads/Pad')
for pad in pads:
    net = pad['Net']
    print(pad['StringNumber'], net['Name'] if net is not None else '(unassigned)')
```

Use `where` for Python comparisons. This query tests stored component origins,
not the visible footprint boundary:

```python
parts = design.select('/Board/Components/Component',
                      where=lambda part: 0 <= part['X'] <= 30 and 0 <= part['Y'] <= 60)
```

Shared lengths are three units per millimetre. Component `Angle` is in radians;
PCB placement permits arbitrary angles. Other angle domains have their own
definitions in the catalogue.

## Constructors

`new_document()` creates a board with top and bottom copper layers. Other
constructors return detached records; append them to their owning collection
before assigning relationships to existing document records. Supply the geometry
and settings needed for the intended object; the constructors do not load a
library definition or generate routing.

| Call | Result |
| --- | --- |
| `new_document()` | A new PCB document |
| `new_component(name='', refdes='')` | A component with an owned empty pattern |
| `new_pad(number='', name='', *, x=0, y=0)` | A physical pad with an authored label and local origin |
| `new_pattern_drawing(*, kind=0)` | A footprint drawing |
| `new_user_field(name='', value='', *, kind=0)` | Component user data and marking settings |
| `new_net(name='')` | A net with membership and trace collections |
| `new_trace()` | A trace with an empty point collection |
| `new_point(*, x=0, y=0, width=-1)` | A trace point in board coordinates |
| `new_layer(name='')` | A copper layer |
| `new_via_style(name='', *, size=0, hole_size=0)` | A via style |
| `new_net_class(name='')` | A net class |
| `new_pair(name='')` | Differential-pair data |
| `new_removed_pair(name='')` | Restorable pair data; no routing is removed or restored by the call |

## Data edits and maintained relationships

Named fields use ordinary Python mapping access. Reads and queries refer to the
same records, so no replacement document or rebuild is needed after an edit.

```python
connector['RefDes'] = design.refdes('J').first_free()
connector['Value'] = 'Signal input'
```

RefDes family helpers share the schematic numbering rules. A bare prefix has
counter zero, and leading zeroes do not create another numeric identity. `R3`
and `R003` therefore cannot be introduced together by an edit. Imported duplicate
labels remain representable. An underscore suffix does not itself establish a
hierarchy link: `HiddenId` and `HierarchyPath` hold that separate information.
Newly authored PCB components start without a schematic association. Imported
explicit identifiers, including zero, retain their meaning.

ASC has position-specific name restrictions. Export warns when a RefDes needs
substitution or the receiving application will reinterpret punctuation.
Copper-layer names preserve ordinary spaces through their ASC spelling, but
cannot distinguish a literal `!` from a space. Their parentheses, quotes and
line breaks also require substitutions. The editable names remain unchanged;
DIP and DIPXML avoid those ASC token restrictions.

Use records as relationship targets. The library derives serialized selectors
from their current ownership and order:

```python
signal = pads[0]['Net']
signal['Name'] = 'INPUT'
signal.move_to(design.one('/Board/Nets'), 0)
assert pads[0]['Net'] is signal
```

Changing `pad['Net']` maintains net membership. Assigning a trace's `Target1` or
`Target2` maintains its connection to that pad or trace point. Contradictory
assignments and unsafe removals fail before changing the model. For example, a
pad cannot be moved to another net while it still contradicts an attached trace.
Related data must be changed or disconnected explicitly.

`MainLengthRule` is the current working length rule. It can select a net class
through `Class`, with its numerical selector maintained automatically. Its name,
limits and connections remain independent working data. Generated class length
results instead belong to `NetClass/LengthResults`; editing either dataset does
not calculate routing lengths.

These are data operations. Moving a component changes its placement; it does
not move existing trace geometry. Changing a pour boundary does not calculate
its fill, and editing copper does not rerun stored design checks. Changing a
library reference does not import a replacement footprint. The model retains
the explicit geometry and results until the caller edits or removes them.

Missing calculated data remains absent. In particular, a filled pour may arrive
without fill geometry from a format that omits it. Export applies the
destination's requirements and reports the resulting adaptation. It does not
calculate missing copper.

Marking settings can describe a component label without a calculated text
drawing, as in XML input. DIP and ASC export complete missing label drawings
from those settings; supplied drawings remain current editable data. XML writes
the settings instead. Text calculations share the library's font services, with
an optional `ExportContext(text_layout=...)` for system-font measurements.

Calculated fill can separately lack its region classification. When available,
`Fill/Regions/Region` records own group labels through `Number`; fill lines,
spokes and polygons use `Region` references to those groups. `Region=None`
means unassigned, and `RegionId` is the read-only output label. Changing a group
label updates its members without a rebuild. Removing a referenced group requires
explicitly disconnecting its members first. None of these edits recalculates fill.

Ordinary file import and saving clear transient interactive routing sessions,
following the editor's normal file workflow. Committed board routing remains;
the library does not resume a paused routing operation or preserve its undo
history as authored design data.

Import also removes degenerate filled board primitives, such as a rectangle
with no height or a filled polygon containing only two points. The report records
this normalization as information, and surviving drawing references remain
coordinated. Ordinary data edits do not run geometric cleanup automatically.

## Optional configuration and diagnostics

Stored settings take precedence over fallback choices. An `ImportContext` supplies
environment choices where the file cannot; an `ExportContext` can override output
units and project paths or supply missing settings. Contexts are immutable;
construct one with the choices needed for that operation.

The default PCB import context assumes a black canvas. Stored drawing colors
that match the canvas receive a visible contrast color during import. Use
`ImportContext(background_color=None)` to retain those stored colors instead.
Later color edits remain ordinary data edits.

```python
from lib import ConversionReport
from lib.pcb import ExportContext

report = ConversionReport()
design = read('board.dip', report=report, label='load')
write(design, 'board.dipxml', context=ExportContext(units='mm'),
      report=report, label='save')
```

A shared report collects notices across operations. Expected normalization and
reconstructable omissions are info; meaningful loss or unresolved constraints
are warnings. Invalid or unimplemented operations report errors and still raise.
`report.clear()` resets the collected notices for another batch. Readable text
formats have their own capabilities: inspect the report when changing formats
or versions rather than assuming every supplied setting has an output slot.

The [PCB examples](../examples/pcb/README.md) create, inspect, edit and convert a
small design. They use the same fields and relationships as imported boards.
