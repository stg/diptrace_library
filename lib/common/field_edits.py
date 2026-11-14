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


def _preview_values(changes):
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
    return values or None


@contextmanager
def preview_values(changes):
    # An empty preview must not force ordinary reads through the projection
    # machinery. An enclosing nonempty preview is already included in values.
    token = _values.set(_preview_values(changes))
    try:
        yield
    finally:
        _values.reset(token)


def _slot_changes(overrides):
    changes = {}
    for (node, argument), value in overrides.items():
        arguments = changes.get(node)
        if arguments is None:
            arguments = changes[node] = list(node.arguments)
        arguments[argument] = value
    return changes.items()


@contextmanager
def preview_slots(overrides):
    with preview_values(_slot_changes(overrides)):
        yield


class PreparedSlots:
    """Reuse one prospective value set while a dependency plan is unchanged.

    This is local to one preflight, never a document cache. The planner must
    invalidate it when an override changes. Each entry restores its enclosing
    preview on exit; actual model values remain untouched.
    """
    def __init__(self, overrides):
        self.overrides = overrides
        self._prepared = False
        self._snapshot = None

    def invalidate(self):
        self._prepared = False

    def __enter__(self):
        if not self._prepared:
            self._snapshot = _preview_values(_slot_changes(self.overrides))
            self._prepared = True
        self._token = _values.set(self._snapshot)
        return self

    def __exit__(self, error_type, error, traceback):
        _values.reset(self._token)


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


def prepare_reference_attachment(document, base, *, specifications=(), issues=()):
    """Combine structural edits and new scoped relationships before attachment."""
    from .references import UnresolvedReference
    from .reference_edits import preview_references
    if not specifications and not issues:
        return base
    graph = document.references
    with preview_slots(base.values):
        additions = graph._prepare_additions(specifications, structure=base)
        with preview_references(graph, {entry.reference.uid: entry.reference for entry in additions.bindings}):
            for source, message, indices, collections, guards in issues:
                graph._validate_reference_guards(UnresolvedReference(source, message, indices, collections, guards), {})
    return ReferenceValueEdit(document, additions, None, tuple(issues))


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
