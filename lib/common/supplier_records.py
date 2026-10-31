"""Supplier identities and ordered price breaks shared by document families."""
from .schema import Child, Field, Record


QUOTE = Record('Quote', {
    'Quantity': Field('Quantity', 'integer', required=True, default=0),
    'Price': Field('Price', 'number', required=True, default=0,
                   description='Unit price in the supplier currency.'),
}, parameters=('Quantity', 'Price'))
PRICES = Record('Prices', {}, description='An ordered collection of Quote records.',
                children={'Quote': Child('Quote', QUOTE.name, maximum=None)})
SUPPLIERS = Record('Suppliers', {
    **{name: Field(name, 'text', default='') for name in
       ('PartNumber', 'Manufacturer', 'Pattern', 'Supplier', 'SourceLocator', 'Currency')},
    'MainSupplier': Field('MainSupplier', 'boolean'),
}, children={'Prices': Child('Prices', PRICES.name)})


def definition(node):
    parent = node.parent
    if parent is None:
        return None
    if node.kind == 'Suppliers' and parent.kind in ('Component', 'Part', 'Pattern'):
        return SUPPLIERS
    if node.kind == 'Prices' and parent.kind == 'Suppliers':
        return PRICES
    if node.kind == 'Quote' and parent.kind == 'Prices':
        return QUOTE
    return None


def requires_attachment(parent, node):
    return (node.schema in (SUPPLIERS, PRICES, QUOTE) or
            parent.kind in ('Component', 'Part', 'Pattern') and node.kind == 'Suppliers' or
            (parent.kind, node.kind) in (('Suppliers', 'Prices'), ('Prices', 'Quote')))


def prepare_attachment(node):
    if definition(node) is not None:
        for child in node.walk(include_self=True):
            if (schema := definition(child)) is not None:
                child.bind_schema(schema)
