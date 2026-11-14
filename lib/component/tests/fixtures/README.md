These are independently authored interoperability controls, not user designs.

`parameters_input.elixml` exercises symbol, pin, footprint, text and model fields;
`parameters.eli` is its canonical binary conversion. `connections_input.elixml`
adds an internal connection between its two pads. Its binary companions cover
ELI 31, 32 and 33; `connections.asc` is the paired ASC export for ELI 31.

The multipart fixtures contain intentionally different descriptions on two parts,
distinct values and simulation models, and one physical footprint. They check
which fields belong to the component and which remain independent per part.
The canonical binary/ASC pairs were produced with installed, licensed DipTrace
4.3.0.5, 4.9.5.0 and 5.3.5.1 respectively. Their ASC declaration remains 31.

`text_input.elixml` supplies distinctive literal and field-selected template text
on two parts. `text_31` and `text_33` are its binary/ASC conversions from 4.3 and
5.3. The editor retains and displays this authored template text rather than
replacing it with a placed component's current field values.

`zero` and `secondary_connections` pair authored XML with canonical ELI/XML from
5.3.5.1. They establish zero as an unassigned selector and the primary part's
ownership of physical internal connections. The secondary-input control produces
a native dropped-reference warning; its exports show the resulting normalization.
