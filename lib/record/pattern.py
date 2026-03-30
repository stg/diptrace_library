from __future__ import annotations

# Intended use:
# Descriptor-only schema for Pattern child records under Part.

PATTERN_CHILD_DESCRIPTOR_V2: dict[str, object] = {
    "record_type": "Pattern",
    "descriptor": "PatternChild.v2",
    "layout_text": [
        "scan[parent]: prelude(12)+marker(0f 42 40 00)+len16le_utf16le_noterm:Name",
    ],
    "scan": {
        "prelude_len": 12,
        "prelude_rule": "0f 42 [40|41|42] [00|01] 3b xx xx xx 3b xx xx xx",
        "marker_hex": "0f 42 40 00",
    },
    "semantics": [
        {"key": "pattern_name", "field": "Name", "priority": 300},
    ],
}

PATTERN_CHILD_DESCRIPTOR_V3: dict[str, object] = {
    "record_type": "Pattern",
    "descriptor": "PatternChild.v3",
    "layout_text": [
        "scan[parent]: prelude(12)+marker(0f 42 41 00)+len16le_utf16le_noterm:Name",
    ],
    "scan": {
        "prelude_len": 12,
        "prelude_rule": "0f 42 [42|44] 01 3b xx xx xx 3b xx xx xx",
        "marker_hex": "0f 42 41 00",
    },
    "semantics": [
        {"key": "pattern_name", "field": "Name", "priority": 200},
    ],
}

PATTERN_CHILD_DESCRIPTORS: list[dict[str, object]] = [
    PATTERN_CHILD_DESCRIPTOR_V2,
    PATTERN_CHILD_DESCRIPTOR_V3,
]
