"""Report supplier projection losses independently of the owning document family."""
from .conversion import info, warn


def report_supplier_omissions(owners, *, destination, report=None,
                              omit_source_locator=True, omit_prices=True, omit_preference=False):
    """Retain chosen suppliers; distinguish authored details from a cached match."""
    locators, quotes, matches = [], [], []
    for owner in owners:
        supplier = owner.child('Suppliers')
        if supplier is None:
            continue
        locator = supplier.child('SourceLocator')
        if omit_source_locator and locator is not None and locator.values and locator.values[0]:
            locators.append(locator)
        if omit_prices:
            quotes.extend(supplier.select('Prices/Quote'))
        flag = supplier.child('MainSupplier')
        if omit_preference and flag is not None and flag.values == (True,):
            matches.append(flag)
    for rule, message, nodes in (
            ('supplier-source-locator', 'Stored supplier source locators are omitted', locators),
            ('supplier-quotes', 'Stored supplier quantity/price rows are omitted', quotes)):
        if nodes:
            warn(report, rule, destination, message, nodes,
                 recoverability='the omitted saved values cannot be recovered from this destination alone; source facts remain intact')
    if matches:
        info(report, 'supplier-preference', destination, 'The cached main-supplier match flag is omitted', matches,
             recoverability='the chosen supplier is retained; its match to a preferred supplier depends on the receiving environment, not the saved cached bit')
