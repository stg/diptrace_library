"""Declared pad construction defaults."""


def empty_pad(index):
    """An explicit empty boundary slot, absent from placed-footprint ASC."""
    from ...common.footprint_objects import new_pad
    pad = new_pad(index=index)
    pad.annotations.update(reserved=True, asc_omit='empty boundary pad',
                           generated_default='boundary pad omitted from ASC')
    return pad
