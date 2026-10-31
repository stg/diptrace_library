"""Replace integral compatibility sizes with authoritative font properties."""

# Positive library font strokes become physical XML lengths at this application
# version. Controlled exports with different library units expose the change.
PHYSICAL_XML_WIDTH_SINCE = (5, 3, 5, 0)


def compatibility_size(value):
    """Generate an integral compatibility size from the authoritative number."""
    from decimal import Decimal
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise TypeError('font size requires a number')
    return round(value)


def read_font_properties(reader, records):
    """Each record supplies its owner, size field and optional mono field."""
    for owner, size, mono in records:
        if mono:
            reader.field(owner, mono, 'boolean', replace=True)
        reader.field(owner, size, 'number', replace=True)


def write_font_properties(writer, records):
    """Write authoritative sizes and optional mono choices in adapter order."""
    for owner, size, mono in records:
        if mono:
            writer.boolean(owner.get(mono, False))
        writer.field(owner, size, 'number')
