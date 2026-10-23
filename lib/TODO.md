# Library development

- The common current schematic model and DCH/ASC/DCHXML adapters are implemented
  under design/MODEL_CONTRACT.txt. Import modernizes; detached export adapts.
  Complete imports use current properties and scoped references, without source
  replay or preservation-only snapshots. Portable tests cover editing, natural
  round trips and repeated-conversion stability.
- Segment-local branch normalization supports longer hosts and coherent pin
  anchors, near-corner retargeting, outside projections and dependent short
  branches. Keep pins fixed and joins on their declared segments. Longer/cyclic
  constraints and unknown compatibility directions retain source data and warn.
- Extend the XML mapping for public variants beyond the supported vocabulary.
  XML automatic marking definitions cannot retain individual appearance overrides
  in the supported readers; conversion warns and retains the authoring data.
  Field-bound authored symbol text refreshes independently of placement/style.
  See design/FORMAT_CAPABILITIES.txt
  for exact adapter limits and conversion consequences.
- Keep capability rules and diagnostics current as adapters expand. Companion
  discovery is outside the single-design-file input boundary. ConversionReport
  spans import and export with shared info/warning/error severities.
- Add coordinated connection editing above the data model.
- Add PCB, component-library and pattern-library adapters.
