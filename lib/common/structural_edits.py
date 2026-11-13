"""Prospective ordering for atomic tree edits, without changing live caches."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from .element_storage import RecordItems


_ordinals = ContextVar('design_prospective_ordinals', default=None)
_structure = ContextVar('design_prospective_structure', default=None)


def ordinal_override(node):
    values = _ordinals.get()
    return values.get(node) if values is not None else None


def parent_override(node, actual):
    state = _structure.get()
    return state[1].get(node, actual) if state is not None else actual


def children_override(node, kind):
    state = _structure.get()
    if state is None or node not in state[0]:
        return None
    children = state[0][node]
    return children if kind is None else tuple(child for child in children if child.kind == kind)


@contextmanager
def preview_ordinals(values):
    if not values:
        yield
        return
    token = _ordinals.set({**(_ordinals.get() or {}), **values})
    try:
        yield
    finally:
        _ordinals.reset(token)


@contextmanager
def preview_structure(children, parents, ordinals):
    if not children and not parents:
        with preview_ordinals(ordinals):
            yield
        return
    previous = _structure.get() or ({}, {})
    token = _structure.set(({**previous[0], **children}, {**previous[1], **parents}))
    try:
        with preview_ordinals(ordinals):
            yield
    finally:
        _structure.reset(token)


def assembling(function):
    """Keep adapter assembly outside authoring-time structural validation."""
    @wraps(function)
    def wrapped(document, *args, **kwargs):
        with assembly(document):
            return function(document, *args, **kwargs)
    return wrapped


@contextmanager
def assembly(document):
    previous = document._automatic_structure
    document._automatic_structure = False
    try:
        yield
    finally:
        document._automatic_structure = previous


class DetachedSnapshot:
    """Restore a detached proposal if schema establishment or preflight fails."""
    def __init__(self, root):
        self.rows = [(node, list(node._items), node._schema, node._children_cache, node._positions_cache,
                      node._dirty, node._reordered, node._parent, node._kind) for node in root.walk(include_self=True)]

    def restore(self):
        for node, items, schema, children, positions, dirty, reordered, parent, kind in self.rows:
            node._schema = schema
            if type(node._content) is RecordItems:
                if schema is None:
                    node._content.replace(())
                    node._content = []
                elif node._content.storage.layout.schema is not schema:
                    node._content.rebind(schema)
            node._items = items
            node._children_cache, node._positions_cache = children, positions
            node._dirty, node._reordered, node._parent = dirty, reordered, parent
            node._kind = kind
        # A child restored from a proposed schema may be a plain field again.
        # Repack after all rows, retaining the original observed field objects.
        for node, *_ in self.rows:
            if type(node._content) is RecordItems:
                node._content.replace(list(node._content))


def validate_child_change(parent, children, kind):
    schema = parent.schema
    if schema is None:
        return
    selected = tuple(child for child in children if child.kind == kind)
    definition = schema.children.get(kind)
    if definition is not None:
        count = len(selected)
        if count < definition.minimum or definition.maximum is not None and count > definition.maximum:
            raise ValueError(f'{kind}: child count would violate the {schema.name} schema')
        if definition.record and any(child.schema is not None and
                child.schema.name not in definition.record.split('|') for child in selected):
            raise TypeError(f'{kind}: expected {definition.record}')
    definition = schema.fields.get(kind)
    if definition is not None:
        if len(selected) > 1 or definition.required and not selected and definition.getter is None:
            raise ValueError(f'{kind}: field count would violate the {schema.name} schema')
        if selected and definition.getter is None:
            values = selected[0].values
            definition.validate(values if definition.kind == 'tuple' else values[0] if len(values) == 1 else values)
