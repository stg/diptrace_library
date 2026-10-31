"""Supplier data and generated-table supplier choices."""
from ....common.supplier_codec import read_supplier


def read_suppliers(reader, board, cached_definitions):
    if reader.header.version > 50:
        for component in board.select('Components/Component'):
            read_supplier(reader, component, prices=True)
        for cached in cached_definitions:
            read_supplier(reader, cached.definition.one('Part'), prices=False)
    if reader.header.version > 51:
        for table in board.select('Tables/Table'):
            reader.field(table, 'Supplier', 'text')
        for component in board.select('Components/Component'):
            reader.field(component.one('Suppliers'), 'MainSupplier', 'boolean')
