from __future__ import annotations

# Intended use:
# Descriptor-only schema for Part records.
# Decoding/encoding execution is handled by apps.lib.codec_segments.

PART_RECORD_DESCRIPTOR: dict[str, object] = {
    "record_type": "Part",
    "descriptor": "Part.v1",
    "decode": "layout",
    # Machine-readable ordered layout consumed by codec.
    "layout": [
        {"name": "unknown1", "format": "bin[4]"},
        {"name": "type", "format": "u8"},
        {"name": "unknown2", "format": "bin[2]"},
        {"name": "show_name", "format": "u8"},
        {"name": "unknown3", "format": "bin[5]"},
        {"name": "page", "format": "u8"},
        {"name": "unknown4", "format": "bin[2]"},
        {"name": "orientation", "format": "u8"},
        {"name": "unknown5", "format": "bin[7]"},
        {"name": "x", "format": "be24_bias1e4"},
        {"name": "unknown6", "format": "bin[1]"},
        {"name": "y", "format": "be24_bias1e4"},
        {"name": "unknown7", "format": "bin[1]"},
        {"name": "width", "format": "be24_bias1e4"},
        {"name": "unknown8", "format": "bin[5]"},
        {"name": "Name", "format": "len16be_utf16be"},
        {"name": "RefDes", "format": "len16be_utf16be"},
        {"name": "Value", "format": "len16be_utf16be"},
        {"name": "BaseRefDes", "format": "len16be_utf16be"},
        {"name": "BaseName", "format": "len16be_utf16be"},
        {"name": "unknown9", "format": "bin[*]"},
    ],
    "required_non_empty_fields": ["RefDes"],
}
