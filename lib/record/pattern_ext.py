from __future__ import annotations

# Intended use:
# Descriptor-only schema for PatternExtension (typed mode=1 sibling) records.

PATTERN_EXTENSION_DESCRIPTOR: dict[str, object] = {
    "record_type": "PatternExtension",
    "descriptor": "PatternExtension.v1",
    "decode": "scan_marker_strings",
    "scan": {
        "prelude_len": 12,
        "prelude_rule": "0f 42 [40|41|42] [00|01] 3b xx xx xx 3b xx xx xx",
        "marker_hex": "0f 42 40 00",
    },
    "semantics": [
        {"key": "pattern_name", "field": "PrimaryName", "priority": 100},
    ],
}
