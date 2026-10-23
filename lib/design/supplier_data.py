"""Explicit export defaults for supplier match flags absent from older inputs."""
from .conversion import info
from .dch_records import placed_components


def prepare_preferences(schematic, *, default=False, destination, report=None):
    """Materialize a required output flag on a detached, older source view.

    The source has no saved match flag. The default is a caller choice, not a
    deduction from a supplier locator or an application's current configuration.
    Existing flags take priority.
    """
    added = []
    for part in placed_components(schematic):
        supplier = part.one('Suppliers')
        if supplier.child('MainSupplier') is None:
            added.append(supplier.add('MainSupplier', default))
    if added:
        info(report, 'supplier-preference-default', destination,
             f'absent saved main-supplier match flags use the configured default {default}', added,
             recoverability='the source has no saved flag; the chosen default is materialized only in this export view')
