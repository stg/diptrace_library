These small libraries were authored for the tests. Their XML inputs contain
fictional names and geometry; the LIB and ASC companions were produced by
importing them into Pattern Editor 5.3.5.1, saving and exporting the libraries.

To reproduce them, import the corresponding `*_input.libxml` into Pattern
Editor and use Save As to write a separate LIB. Generated library identities
can differ. `example.step` is an intentionally unavailable model filename;
the fixture tests its reference and placement data without loading a model.

The geometry fixture exercises pads, drawing and hole groups, and dimensions
attached to different local object types. The metadata fixture exercises
multiline text, monospace and fractional font size, drawing-to-pad selection,
supplier names, and distinct nonzero model transforms. Expected import
normalization is checked as data rather than by binary equality.
