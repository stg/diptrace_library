# diptrace_reparse

Reads a DipTrace `.dch` through the structural tree model and writes it back as binary.

Current scope:
- byte-accurate round-trip for unchanged trees
- useful as a baseline while record-level encoders are expanded

Usage:

```bash
python apps/dch_reparse/reparse_dch.py input.dch output.dch --verify
```

