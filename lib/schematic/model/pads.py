"""Declared pad construction defaults."""


def empty_pad(index):
    """An explicit empty boundary slot, absent from placed-footprint ASC."""
    from ...common.footprint_objects import new_pad
    pad = new_pad(index=index)
    return pad
