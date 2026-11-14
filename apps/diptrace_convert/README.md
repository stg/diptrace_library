# Format and version conversion

Convert a design by recognizing its input content and selecting the output format
from its extension:

```sh
python -m apps.diptrace_convert input.dch output.dchxml
python -m apps.diptrace_convert input.dchxml output.dch --version 52
```

Inputs need no particular extension: a DipTrace XML export named `input.xml`
works too.

The same command converts between versions of one format using different input
and output paths. Supported combinations and default versions come from the
[library's capability tables](../../README.md); the app keeps no separate version
list. The command works with schematics, PCB layouts, component libraries and
pattern libraries. Conversion stays within the input document's family.

For example, convert a component library to XML for an older supported release:

```sh
python -m apps.diptrace_convert parts.eli parts.elixml --version 4.3.0.5
```

`--version` selects the destination version using the adapter's own selector:
a schema number, or an application release where the format uses one directly.
For DCHXML, the schema also selects the corresponding XML dialect. An unsupported
version fails before writing output. Without it, the library's default output
version is used.

`--context FILE` supplies optional JSON export overrides. Start with
[context.example.json](context.example.json); its keys correspond to the
[library's export context](../../doc/GETTING_STARTED.md). Common options apply
across formats; destination-specific options must suit the output format. The
JSON loader also accepts `text_layout`. The schematic ASC loader additionally
accepts `line_widths` and `default_line_width`; PCB uses a numeric `line_width`
fallback. Context fields belong to the detected family: for example, PCB text
fallbacks use `font_size`/`vector_font`, not the schematic `marking_style`.
Component and pattern libraries share the context described in the
[library guide](../../doc/LIBRARIES.md#output-choices-and-diagnostics).
`--windows-fonts` selects the Windows provider for system-font measurements.

The app finishes import and serialization before opening its output. Input and
output must be different files. For general command conventions, diagnostic
filtering and exit codes, see [the application guide](../README.md#command-output).
