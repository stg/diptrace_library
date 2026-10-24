Implementation references
=========================

These plain-text files support AI-assisted development and precise implementation
work. They complement the human Markdown documentation; they are not prerequisites
for using the library.

Human documentation:
  ../doc/GETTING_STARTED.md   Short read/edit/write introduction.
  ../doc/API.md               Supported operations, options and working examples.
  ../doc/MODEL.md             Design meaning, ownership and editing guarantees.
  ../doc/SCHEMATIC.md         Single generated field/ownership catalogue.

Implementation material:
  API_NOTES.txt              Adapter and advanced-operation notes.
  MODEL_CONTRACT.txt         Architecture and design/conversion invariants.
  FORMAT_CAPABILITIES.txt    Mapping limits and diagnostic classifications.
  DEVELOPMENT.txt            Development record; not an active TODO list.

Keep distinct contracts and implementation detail here. Link to the catalogue
in doc/ rather than maintaining another copy. SCHEMATIC.md is generated from the
same immutable schematic_schema() definitions used by the model.
