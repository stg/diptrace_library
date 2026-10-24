# Format and version conversion

Convert a design using the input and output extensions to select its formats:

```sh
python -m apps.diptrace_convert input.dch output.dchxml
python -m apps.diptrace_convert input.dchxml output.dch --version 52
```

The same command converts between versions of one format using different input
and output paths. Supported combinations and default versions come from the
[library's capabilities](../../README.md#schematics); the app keeps no separate
version list. Currently, DCH, ASC and DCHXML schematics are supported.

`--version` selects the destination schema, including the corresponding XML
dialect for DCHXML. An unsupported version fails before writing output. Without
it, the library's default output version is used.

`--context FILE` supplies optional JSON export overrides. Start with
[context.example.json](context.example.json); its keys correspond to the
[library's export context](../../doc/GETTING_STARTED.md). Common options apply
across formats; destination-specific options must suit the output format. The
JSON loader also accepts `text_layout`, `line_widths` and `default_line_width`.
`--windows-fonts` selects the Windows provider for system-font measurements.

The app finishes import and serialization before opening its output. Input and
output must be different files. For general command conventions, diagnostic
filtering and exit codes, see [the application guide](../README.md#command-output).
