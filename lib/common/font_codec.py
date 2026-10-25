"""Replace integral compatibility sizes with authoritative font properties."""


def read_font_properties(reader, records):
    """Each record supplies its owner, size field and optional mono field."""
    for owner, size, mono in records:
        if mono:
            reader.field(owner, mono, 'boolean', replace=True)
        reader.field(owner, size, 'number', replace=True)
