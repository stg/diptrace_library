"""Routing defaults expose the default class's authoritative width/clearance."""
from ...common.schema import Field, Record
from .relationships import linked


def default_row(settings):
    document = settings._owner()
    board = document.one('/Board') if document is not None else None
    net_class = linked(board, 'default-net-class') if board is not None else None
    properties = net_class.child('LayProperties') if net_class is not None else None
    rows = properties.children('LayProperty') if properties is not None else ()
    return rows[0] if rows else None


def _relationships(settings):
    document = settings._owner()
    return ((document.one('/Board'), 'default-net-class', 'outgoing'),) if document is not None else ()


def _collections(settings):
    document = settings._owner()
    board = document.one('/Board') if document is not None else None
    net_class = linked(board, 'default-net-class') if board is not None else None
    properties = net_class.child('LayProperties') if net_class is not None else None
    dependencies = []
    if net_class is not None:
        dependencies.append((net_class, 'LayProperties'))
    if properties is not None:
        dependencies.append((properties, 'LayProperty'))
    return tuple(dependencies)


def _set(settings, name, value):
    row = default_row(settings)
    if row is None:
        raise ValueError('routing defaults require a default class with layer properties')
    row[name] = value


def _alias(name, target):
    return Field(name, 'number', nullable=True, unit='shared length',
        getter=lambda settings: row.get(target) if (row := default_row(settings)) is not None else None,
        setter=lambda settings, value: _set(settings, target, value),
        reference_dependencies=_relationships, collection_dependencies=_collections,
        value_dependencies=lambda settings: ((row, target),) if (row := default_row(settings)) is not None else ())


ROUTING = Record('PcbRoutingSettings', {
    'TraceWidth': _alias('TraceWidth', 'Width'),
    'TraceClearance': _alias('TraceClearance', 'Clearance'),
    **{name: Field(name, 'number', default=0, unit='shared length') for name in
       ('PadClearance', 'BoardClearance', 'ViaSize', 'FanoutLength', 'ViaHole')},
    'Router': Field('Router', 'integer', default=0), 'ViaApply': Field('ViaApply', 'integer', default=0),
})
