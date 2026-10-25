"""Prospective field values and prepared named edits, without live mutation."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from .structural_edits import preview_structure


_values = ContextVar('design_prospective_field_values', default=None)


def proposed_arguments(node):
    values = _values.get()
    return values.get(node) if values is not None else None


def named_field(node, argument):
    if node.parent is not None and node.parent.schema is not None and node.kind in node.parent.schema.fields:
        return node.parent, node.kind
    if node.schema is not None and isinstance(argument, int) and 0 <= argument < len(node.schema.parameters):
        return node, node.schema.parameters[argument]
    return None


@contextmanager
def preview_values(changes):
    values = dict(_values.get() or ())
    for node, supplied in changes:
        supplied = tuple(supplied)
        values[node] = supplied
        if node.schema is not None:
            for index, name in enumerate(node.schema.parameters):
                if index < len(supplied) and node.schema.fields[name].getter is None:
                    child = node.child(name)
                    if child is not None:
                        values[child] = (supplied[index],)
    token = _values.set(values)
    try:
        yield
    finally:
        _values.reset(token)


@contextmanager
def preview_slots(overrides):
    changes = {}
    for (node, argument), value in overrides.items():
        arguments = changes.setdefault(node, list(node.arguments))
        arguments[argument] = value
    with preview_values(changes.items()):
        yield


@contextmanager
def field_proposal(record, name, values):
    from .model import Element
    field = record.child(name)
    created = field is None
    if created:
        field = Element(name, *values)
        children = (*record._child_sequence(), field)
        position = len(record._child_sequence(name))
        with preview_structure({record: children}, {field: record}, {field: position}):
            with preview_values(((field, values),)):
                yield field, created
    else:
        with preview_values(((field, values),)):
            yield field, created


@dataclass
class ValueEdit:
    document: object
    projections: object
    derived: object
    parent: object = None

    def apply(self):
        self.document.references.apply_value_change(self.projections)
        self.document._apply_field_change(self.derived)
        if self.parent is not None:
            self.document.references.finish_structure((self.parent,))


@dataclass
class ReferenceValueEdit:
    """Commit a named edit that also activates newly meaningful relationships."""
    document: object
    additions: object
    derived: object
    issues: tuple
    parent: object = None

    def apply(self):
        graph = self.document.references
        graph._apply_additions(self.additions)
        self.document._apply_field_change(self.derived)
        for source, message, indices, collections, guards in self.issues:
            graph.note(source, message, *indices, collections=collections, guards=guards)
        if self.parent is not None:
            graph.finish_structure((self.parent,))


def prepare_reference_edit(document, record, field, values, *, created, base,
                           specifications=(), issues=()):
    """Preflight values and newly activated links as one atomic named edit."""
    from .references import UnresolvedReference
    graph = document.references
    with preview_slots(base.projections.values):
        additions = graph._prepare_additions(specifications, structure=base.projections)
        requested = {field._argument_owner(index): value for index, value in enumerate(values)}
        graph._validate_requested_values(requested, additions.projections, additions=additions.bindings)
        for source, message, indices, collections, guards in issues:
            graph._validate_reference_guards(UnresolvedReference(source, message, indices, collections, guards), {})
    return ReferenceValueEdit(document, additions, base.derived, tuple(issues), record if created else None)
