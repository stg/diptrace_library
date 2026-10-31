"""Supplier identities and optional price breaks shared by design families."""


def read_supplier(reader, owner, *, prices):
    supplier = owner.add('Suppliers')
    for name in ('PartNumber', 'Manufacturer', 'Pattern', 'Supplier', 'SourceLocator', 'Currency'):
        reader.field(supplier, name, 'text')
    if prices:
        quotes = supplier.add('Prices')
        for _ in range(reader.count('supplier price breaks')):
            reader.record(quotes, 'Quote', 'integer', 'number')
    return supplier


def write_supplier(writer, owner, *, prices):
    supplier = owner.child('Suppliers')
    for name in ('PartNumber', 'Manufacturer', 'Pattern', 'Supplier', 'SourceLocator', 'Currency'):
        writer.text(supplier.get(name, '') if supplier is not None else '')
    if prices:
        writer.rows(supplier.child('Prices') if supplier is not None else None, 'Quote', 'integer number')
