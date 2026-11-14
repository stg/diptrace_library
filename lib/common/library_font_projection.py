"""Detached font-size adaptation for older standalone-library receivers."""
from .conversion import warn
from .font_codec import compatibility_size


def round_sizes(records, *, destination, report=None):
    """Project ``(owner, field name)`` pairs to integral receiver sizes."""
    for owner, name in records:
        size = owner[name]
        rounded = compatibility_size(size)
        if size != rounded:
            owner[name] = rounded
            warn(report, 'fractional-font-size', destination,
                 'Destination font sizes are rounded to integral values', (owner,))
