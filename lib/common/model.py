"""Our editable document tree, independent of any binary serializer or layout.

An element contains an ordered mixture of values and child elements. This
retains duplicate fields, tuple arguments, empty containers and ordering without
forcing a source format's private object layout onto the public API.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from copy import deepcopy
from functools import lru_cache
import math
import re
from typing import Callable, Iterator
from uuid import uuid4
from .schema import MISSING
from .field_edits import proposed_arguments, field_proposal, ValueEdit, _values as _prospective_values
from .structural_edits import (ordinal_override, parent_override, children_override, validate_child_change,
                               preview_structure, DetachedSnapshot, assembly,
                               _structure as _prospective_structure, _ordinals as _prospective_ordinals)


Scalar = str | int | Decimal | bool | None
ELEMENT_NAME = r"[A-Za-z_][A-Za-z_0-9.-]*"
_NAME = re.compile(ELEMENT_NAME + r"\Z")
_SYMBOL = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z")
_EMPTY_CHILDREN = {None: ()}


@lru_cache(maxsize=1024)
def _valid_element_name(kind):
    """Cache syntax checks, never mutable element state."""
    return _NAME.fullmatch(kind) is not None


@dataclass(frozen=True)
class SourceSpan:
    format: str
    start: int
    end: int
    source: str | None = None


@dataclass(frozen=True)
class Value:
    value: Scalar
    kind: str
    unit: str = ""
    lexeme: str | None = None
    source: SourceSpan | None = None

    @classmethod
    def of(cls, value: Scalar | float | "Value", *, symbol: bool = False, unit: str = "") -> "Value":
        if isinstance(value, Value):
            return value
        if value is None:
            return cls(None, 'null')
        if symbol:
            if not isinstance(value, str) or not _SYMBOL.fullmatch(value):
                raise ValueError("symbols must be identifiers")
            return cls(value, "symbol")
        if isinstance(value, bool):
            return cls(value, "boolean")
        if isinstance(value, str):
            return cls(value, "string")
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError("numbers must be finite")
            value = Decimal(str(value))
        if isinstance(value, Decimal) and not value.is_finite():
            raise ValueError("numbers must be finite")
        if isinstance(value, (int, Decimal)):
            if unit not in ("", "%"):
                raise ValueError(f"unsupported numeric unit: {unit!r}")
            return cls(value, "number", unit)
        raise TypeError(f"unsupported value: {type(value).__name__}")


class Element:
    # Most designs contain many scalar-field elements. Keep their fixed state
    # compact while retaining custom attributes and weak references.
    __slots__ = ('_uid', '_kind', '_items', '_children_cache', '_positions_cache',
                 '_schema', '_document', '_parent', 'source', 'annotations',
                 '_syntax', '_dirty', '_reordered', '__dict__', '__weakref__')

    def __init__(self, kind: str, *values: Scalar | float | Value, source: SourceSpan | None = None):
        if kind and not _valid_element_name(kind):
            raise ValueError(f"invalid element kind: {kind!r}")
        self._uid = uuid4().hex
        self._kind = kind
        self._items: list[Element | Value] = [Value.of(v) for v in values]
        self._children_cache = None
        self._positions_cache = None
        self._schema = None
        self._document = None
        self._parent: Element | None = None
        self.source = source
        self.annotations: dict[str, object] = {}
        self._syntax = None
        self._dirty = True
        self._reordered = True

    @property
    def uid(self) -> str:
        return self._uid

    @property
    def kind(self) -> str:
        return self._kind

    @kind.setter
    def kind(self, kind: str):
        if not _valid_element_name(kind):
            raise ValueError(f"invalid element kind: {kind!r}")
        if self._kind != kind:
            self._kind = kind
            if self._parent is not None:
                self._parent._children_cache = None
                self._parent._positions_cache = None
            self._touch()

    @property
    def type(self) -> str:
        """Familiar query vocabulary from the earlier library API."""
        return self.kind

    @property
    def parent(self) -> "Element | None":
        if _prospective_structure.get() is None:
            return self._parent
        return parent_override(self, self._parent)

    @property
    def changed(self) -> bool:
        """Whether this element or any descendant changed since loading."""
        return self._dirty

    @property
    def items(self) -> tuple["Element | Value", ...]:
        return tuple(self._items)

    @property
    def arguments(self) -> tuple[Value, ...]:
        if _prospective_values.get() is None:
            return self._stored_arguments()
        proposed = proposed_arguments(self)
        return proposed if proposed is not None else self._stored_arguments()

    def _stored_arguments(self):
        if len(self._items) == 1 and isinstance(self._items[0], Value):
            direct = (self._items[0],)
        else:
            direct = tuple(i for i in self._items if isinstance(i, Value))
        if self._schema is None or not self._schema.parameters:
            return direct
        named = []
        for name in self._schema.parameters:
            definition = self._schema.fields[name]
            if definition.getter is not None:
                named.append(Value.of(definition.getter(self)))
            else:
                child = self.child(name)
                named.append(child.arguments[0] if child is not None else Value.of(definition.default))
        return tuple(named) + direct

    @property
    def values(self) -> tuple[Scalar, ...]:
        return tuple(v.value for v in self.arguments)

    @property
    def path(self) -> str:
        parts = []
        node = self
        while node.parent is not None:
            parts.append(f"{node.kind}[{node._ordinal()+1}]")
            node = node.parent
        return "/" + "/".join(reversed(parts))

    def _touch(self, *, reordered=False):
        self._reordered |= reordered
        if reordered:
            self._children_cache = None
            self._positions_cache = None
        node: Element | None = self
        while node is not None:
            node._dirty = True
            if reordered and node._document is not None:
                node._document._identity_index = None
            node = node._parent

    def _child_sequence(self, kind=None):
        """Private immutable lookup; public callers receive independent lists."""
        if _prospective_structure.get() is not None:
            prospective = children_override(self, kind)
            if prospective is not None:
                return prospective
        if self._children_cache is not None:
            return self._children_cache.get(kind, ())
        return self._stored_child_sequence(kind)

    def _stored_child_sequence(self, kind=None):
        if self._children_cache is None:
            children = tuple(item for item in self._items if isinstance(item, Element))
            if children:
                groups = {}
                for child in children:
                    groups.setdefault(child.kind, []).append(child)
                self._children_cache = {name: tuple(rows) for name, rows in groups.items()}
                self._children_cache[None] = children
            else:
                self._children_cache = _EMPTY_CHILDREN
        return self._children_cache.get(kind, ())

    def children(self, kind: str | None = None) -> list["Element"]:
        return list(self._child_sequence(kind))

    def child(self, kind: str) -> "Element | None":
        return next(iter(self._child_sequence(kind)), None)

    def _ordinal(self):
        if _prospective_ordinals.get() is not None:
            prospective = ordinal_override(self)
            if prospective is not None:
                return prospective
        return self._stored_ordinal()

    def _stored_ordinal(self):
        if self._parent is None:
            return 0
        parent = self._parent
        if parent._positions_cache is None:
            parent._positions_cache = {}
        if self.kind not in parent._positions_cache:
            parent._positions_cache[self.kind] = {
                child: index for index, child in enumerate(parent._stored_child_sequence(self.kind))}
        return parent._positions_cache[self.kind][self]

    @property
    def schema(self):
        """Immutable named field definitions for this record, when established."""
        return self._schema

    def bind_schema(self, schema):
        """Establish named storage; positional adapter values become projections."""
        if self._schema is schema:
            return self
        if self._schema is not None:
            if self._schema.parameters != schema.parameters:
                raise ValueError('record already has an incompatible parameter schema')
            self._schema = schema
            return self
        raw = tuple(item for item in self._items if isinstance(item, Value))
        plan = []
        for index, name in enumerate(schema.parameters):
            definition = schema.fields[name]
            if definition.getter is not None:
                continue
            existing = self.child(name)
            if index < len(raw):
                value = raw[index]
            elif existing is not None and len(existing.arguments) == 1:
                value = existing.arguments[0]
            elif definition.default is not MISSING:
                value = Value.of(definition.default)
            else:
                raise ValueError(f'{name} is a required record parameter')
            if existing is not None:
                if existing.values != (value.value,):
                    raise ValueError(f'{self.path}: conflicting values for {name}')
            else:
                definition.validate(value.value)
                plan.append((name, value))
        self._items = list(raw[len(schema.parameters):]) + self.children()
        self._schema = schema
        self._touch(reordered=True)
        for name, value in plan:
            self.add(name, value)
        return self

    def _argument_owner(self, index):
        if self._schema is not None and 0 <= index < len(self._schema.parameters):
            name = self._schema.parameters[index]
            if self._schema.fields[name].getter is not None:
                return self, index
            return self.one(name), 0
        # Unnamed adapter-tail slots retain their projected argument number.
        # Consumers read this pair through ``arguments``, which includes the
        # named header. Subtracting its length would alias a header slot.
        return self, index

    def _owner(self):
        root = self
        while root.parent is not None:
            root = root.parent
        return root._document

    def __getitem__(self, name):
        if not isinstance(name, str):
            raise TypeError('field names must be strings')
        definition = self._schema.fields.get(name) if self._schema is not None else None
        if definition is not None:
            if definition is not None and definition.getter is not None:
                return definition.getter(self)
        child = self.child(name)
        if child is None:
            raise KeyError(name)
        if ((self._schema is not None and name in self._schema.children) or
                child._child_sequence() and not (definition is not None and definition.kind == 'tuple')):
            raise TypeError(f'{name} is a child record or collection; use child()')
        values = child.values
        return values if definition is not None and definition.kind == 'tuple' else (
            values[0] if len(values) == 1 else values)

    def get(self, name, default=None):
        try:
            return self[name]
        except KeyError:
            return default

    def __contains__(self, name):
        if not isinstance(name, str):
            return False
        return (self.child(name) is not None or self._schema is not None and
                name in self._schema.fields and self._schema.fields[name].getter is not None)

    def set(self, name, value):
        if self._schema is None:
            raise TypeError('named assignment requires a record schema')
        definition = self._schema.fields[name]
        definition.validate(value)
        if definition.setter is not None:
            definition.setter(self, value)
            return
        supplied = value if definition.kind == 'tuple' else (value,)
        converted = tuple(Value.of(item) for item in supplied)
        child = self.child(name)
        owner = self._owner()
        if child is not None and owner is not None:
            if any(owner.references.manages(child, index) or owner.references.unresolved_slot(child, index)
                   for index in range(len(child.arguments))):
                raise ValueError(f'{name} is reference-managed; edit its relationship instead')
        if owner is None:
            self.set_field(name, *converted)
            return
        with field_proposal(self, name, converted) as (field, created):
            plan = owner._prepare_value_edit(self, name, field, converted, created=created)
        with assembly(owner):
            if created:
                self.append(field)
            else:
                field.set_values(*converted)
        plan.apply()

    def __setitem__(self, name, value):
        self.set(name, value)

    def __delitem__(self, name):
        if (self._schema is not None and name in self._schema.fields and
                self._schema.fields[name].getter is not None):
            raise TypeError(f'{name} is a calculated or relationship field and cannot be removed')
        child = self.child(name)
        if child is None:
            raise KeyError(name)
        if self._schema is None:
            raise TypeError('named deletion requires a record schema')
        definition = self._schema.fields[name]
        if definition.required or definition.readonly:
            raise TypeError(f'{name} is required or calculated and cannot be removed')
        owner = self._owner()
        if owner is not None:
            graph = owner.references
            if (any(graph.manages(child, index) or graph.unresolved_slot(child, index)
                    or graph.value_consumers(child, index)
                    or graph.guard_consumers(child, index)
                    or graph.unresolved_guard_consumers(child, index)
                    for index in range(len(child.arguments))) or graph.guard_consumers(child)
                    or graph.unresolved_guard_consumers(child) or graph.incoming(child) or graph.outgoing(child)):
                raise ValueError(f'{name} is reference-managed and cannot be removed')
        children = tuple(item for item in self._child_sequence() if item is not child)
        with preview_structure({self: children}, {child: None}, {}):
            plan = owner._plan_field_change(self, name, ()) if owner is not None else None
            projections = owner.references.plan_value_changes(owner._field_plan_values(plan)) if owner is not None else ()
        child.detach()
        if owner is not None:
            owner.references.apply_value_change(projections)
            owner._apply_field_change(plan)

    def find(self, kind: str) -> "Element | None":
        return self.child(kind)

    def find_all(self, kind: str | None = None, *, recursive=False,
                 where: Callable[["Element"], bool] | None = None) -> list["Element"]:
        from .query import filter_matches
        nodes = self.descendants(kind) if recursive else self.children(kind)
        return filter_matches(nodes, where)

    def walk(self, *, include_self=False) -> Iterator["Element"]:
        stack = [self] if include_self else list(reversed(self._child_sequence()))
        while stack:
            node = stack.pop()
            yield node
            stack.extend(reversed(node._child_sequence()))

    def descendants(self, kind: str | None = None) -> list["Element"]:
        return [n for n in self.walk() if kind is None or n.kind == kind]

    def select(self, path: str, *, where=None) -> list["Element"]:
        from .query import (select)
        return select(self, path, where=where)

    def one(self, path: str, *, where=None) -> "Element":
        matches = self.select(path, where=where)
        if len(matches) != 1:
            raise LookupError(f"expected one match for {path!r}, found {len(matches)}")
        return matches[0]

    def scalar(self, name: str, default=None, *, occurrence=0):
        definition = self._schema.fields.get(name) if self._schema is not None else None
        if occurrence == 0 and self._schema is not None:
            if definition is not None and definition.getter is not None:
                return definition.getter(self)
        matches = self._child_sequence(name)
        if occurrence >= len(matches):
            return default
        node = matches[occurrence]
        if ((self._schema is not None and name in self._schema.children) or
                node._child_sequence() and not (definition is not None and definition.kind == 'tuple')):
            raise ValueError(f"{node.path} is a container, not a scalar field")
        values = node.values
        return values if definition is not None and definition.kind == 'tuple' else (
            values[0] if len(values) == 1 else values)

    def set_argument(self, index: int, value: Scalar | float | Value) -> "Element":
        if self._schema is not None and self._schema.parameters:
            if index < 0:
                index += len(self.arguments)
            if index < len(self._schema.parameters):
                name = self._schema.parameters[index]
                definition = self._schema.fields[name]
                if definition.getter is not None:
                    # Adapter occurrences do not override calculated model facts.
                    Value.of(value)
                else:
                    definition.validate(Value.of(value).value)
                    self.set_field(name, value)
                return self
            index -= len(self._schema.parameters)
        positions = [i for i, item in enumerate(self._items) if isinstance(item, Value)]
        position = positions[index]
        replacement = Value.of(value)
        previous = self._items[position]
        if ((previous.value, previous.kind, previous.unit) != (replacement.value, replacement.kind, replacement.unit)
                or isinstance(value, Value) and previous != replacement):
            self._items[position] = replacement
            self._touch()
        return self

    def set_values(self, *values: Scalar | float | Value) -> "Element":
        if self._schema is not None and self._schema.parameters:
            count = len(self._schema.parameters)
            if len(values) < count:
                raise ValueError('named record adapter values cannot omit required parameters')
            replacements = tuple(Value.of(value) for value in values)
            for name, value in zip(self._schema.parameters, replacements):
                definition = self._schema.fields[name]
                if definition.getter is None:
                    definition.validate(value.value)
            for index, value in enumerate(replacements[:count]):
                self.set_argument(index, value)
            self._items = list(replacements[count:]) + self.children()
            self._touch(reordered=True)
            return self
        replacements = [Value.of(v) for v in values]
        positions = [i for i, item in enumerate(self._items) if isinstance(item, Value)]
        if len(positions) == len(replacements):
            changed = False
            for i, value, supplied in zip(positions, replacements, values):
                old = self._items[i]
                if ((old.value, old.kind, old.unit) != (value.value, value.kind, value.unit)
                        or isinstance(supplied, Value) and old != value):
                    self._items[i] = value
                    changed = True
            if changed:
                self._touch()
        else:
            self._items = replacements + self.children()
            self._touch(reordered=True)
        return self

    def set_field(self, name: str, *values: Scalar | float | Value, occurrence=0) -> "Element":
        matches = self.children(name)
        if occurrence < 0 or occurrence > len(matches):
            raise IndexError(occurrence)
        if occurrence == len(matches):
            node = self.append(Element(name, *values))
        else:
            node = matches[occurrence]
            definition = self._schema.fields.get(name) if self._schema is not None else None
            if node.children() and not (definition is not None and definition.kind == 'tuple'):
                raise ValueError(f"{node.path} is a container; edit its children explicitly")
            node.set_values(*values)
        return node

    def insert(self, node: "Element", index: int | None = None) -> "Element":
        """Attach a detached child; index addresses child order, excluding values."""
        if not isinstance(node, Element) or not node.kind:
            raise TypeError("child must be a named Element")
        ancestor: Element | None = self
        while ancestor is not None:
            if ancestor is node:
                raise ValueError("cannot create a parent cycle")
            ancestor = ancestor.parent
        if node.parent is not None:
            raise ValueError("child is already attached; use move_to or clone")
        if index is None:
            position = len(self._items)
        else:
            children = self._child_sequence()
            if not 0 <= index <= len(children):
                raise IndexError(index)
            position = self._items.index(children[index]) if index < len(children) else len(self._items)
        owner = self._owner()
        plan = ()
        attachment = None
        if owner is not None and owner._automatic_structure:
            declared = self.schema is not None and (node.kind in self.schema.fields or node.kind in self.schema.children)
            needs_plan = owner.references.collection_requires_plan(self, node.kind)
            activate = owner._attachment_required(self, node)
            if declared or needs_plan or activate:
                children = self.children()
                children.insert(len(children) if index is None else index, node)
                validate_child_change(self, children, node.kind)
                if needs_plan and not activate:
                    plan = owner.references.plan_collections({self: tuple(children)}, parents={node: self})
                if activate:
                    snapshot = DetachedSnapshot(node)
                    counts, ordinals = {}, {}
                    for child in children:
                        ordinals[child] = counts.get(child.kind, 0)
                        counts[child.kind] = ordinals[child] + 1
                    try:
                        with preview_structure({self: tuple(children)}, {node: self}, ordinals):
                            attachment = owner._plan_attachment(self, node, None)
                    except BaseException:
                        snapshot.restore()
                        raise
        cached_children = self._children_cache
        if (position == len(self._items) and cached_children is not None
                and node.kind not in cached_children):
            # New field kinds can extend the lookup without regrouping siblings.
            # Copy it: detached edit snapshots may still share the old cache.
            cached_children = {**cached_children, None: cached_children[None] + (node,),
                               node.kind: (node,)}
        else:
            cached_children = None
        self._items.insert(position, node)
        node._parent = self
        self._touch(reordered=True)
        self._children_cache = cached_children
        if owner is not None:
            if attachment is None:
                owner.references.apply_value_change(plan)
            else:
                owner._apply_attachment(attachment)
            if owner._automatic_structure:
                owner.references.finish_structure((self,))
        return node

    def append(self, node: "Element") -> "Element":
        return self.insert(node)

    def add(self, kind: str, *values: Scalar | float | Value) -> "Element":
        return self.append(Element(kind, *values))

    def detach(self) -> "Element":
        if self.parent is not None:
            parent = self.parent
            owner = self._owner()
            plan = ()
            removed = ()
            if owner is not None and owner._automatic_structure:
                removed = owner.references.check_removal(self)
                declared = parent.schema is not None and (self.kind in parent.schema.fields or self.kind in parent.schema.children)
                needs_plan = owner.references.collection_requires_plan(parent, self.kind)
                if declared or needs_plan:
                    children = tuple(child for child in parent._child_sequence() if child is not self)
                    validate_child_change(parent, children, self.kind)
                    if needs_plan:
                        plan = owner.references.plan_collections({parent: children}, parents={self: None})
            parent._items.remove(self)
            self._parent = None
            parent._touch(reordered=True)
            if owner is not None:
                owner.references.apply_value_change(plan)
                if owner._automatic_structure:
                    owner.references.finish_structure((parent,), removed=removed)
        return self

    def remove(self, child: "Element") -> "Element":
        if child.parent is not self:
            raise ValueError("element is not a child of this parent")
        return child.detach()

    def move_to(self, parent: "Element", index: int | None = None) -> "Element":
        ancestor: Element | None = parent
        while ancestor is not None:
            if ancestor is self:
                raise ValueError("cannot move an element inside itself")
            ancestor = ancestor.parent
        limit = len(parent.children()) - int(self.parent is parent)
        if index is not None and not 0 <= index <= limit:
            raise IndexError(index)  # Validate before detaching: failed moves are atomic.
        if parent is self.parent:
            children = parent.children()
            children.remove(self)
            children.insert(len(children) if index is None else index, self)
            if tuple(children) == parent._child_sequence():
                return self
            owner = self._owner()
            if owner is not None and owner._automatic_structure:
                owner._validate_move(self, parent)
                plan = owner.references.plan_reorder(parent, children)
            else:
                plan = ()
            # Keep the existing value positions, even in syntax inspection views.
            ordered = iter(children)
            parent._items = [next(ordered) if isinstance(item, Element) else item for item in parent._items]
            parent._touch(reordered=True)
            if owner is not None:
                owner.references.apply_value_change(plan)
                if owner._automatic_structure:
                    owner.references.finish_structure((parent,))
            return self
        owner = self._owner()
        destination = parent._owner()
        if self.parent is None:
            return parent.insert(self, index)
        previous = self.parent
        previous_children = tuple(child for child in previous._child_sequence() if child is not self)
        next_children = parent.children()
        next_children.insert(len(next_children) if index is None else index, self)
        moved = tuple(self.walk(include_self=True))
        changes = {previous: previous_children, parent: tuple(next_children)}
        plans = []
        if owner is not None and owner._automatic_structure:
            owner._validate_move(self, parent)
            validate_child_change(previous, previous_children, self.kind)
            if owner is not destination:
                owner.references.check_removal(self)
            plans.append((owner, owner.references.plan_collections(changes, parents={self: parent}, moved=moved)))
        if destination is not None and destination._automatic_structure:
            validate_child_change(parent, next_children, self.kind)
            if destination is not owner:
                plans.append((destination, destination.references.plan_collections(changes, parents={self: parent}, moved=moved)))
        previous._items.remove(self)
        previous._touch(reordered=True)
        children = parent._child_sequence()
        position = parent._items.index(children[index]) if index is not None and index < len(children) else len(parent._items)
        parent._items.insert(position, self)
        self._parent = parent
        parent._touch(reordered=True)
        for document, plan in plans:
            document.references.apply_value_change(plan)
            document.references.refresh_structure(moved)
            document.references.finish_structure(changes, removed=moved if document is owner and owner is not destination else ())
        return self

    def clone(self) -> "Element":
        """Copy content and formatting with fresh identities and no shared children."""
        return self._clone()

    def _clone(self, mapping=None):
        """Collect document ownership mappings during the copy traversal."""
        result = Element(self.kind, source=self.source)
        if mapping is not None:
            mapping[self] = result
        if self.annotations:
            result.annotations = deepcopy(self.annotations)
        result._items = []
        for item in self._items:
            if isinstance(item, Element):
                copied = item._clone(mapping)
                copied._parent = result
                result._items.append(copied)
            else:
                result._items.append(item)  # Values and source spans are immutable.
        result._syntax = self._syntax
        result._schema = self._schema
        result._dirty, result._reordered = self._dirty, self._reordered
        return result

    def inspect(self) -> dict:
        return {"uid": self.uid, "kind": self.kind, "path": self.path,
                "values": [{"value": v.value, "kind": v.kind, "unit": v.unit,
                            "source": v.source} for v in self.arguments],
                "source": self.source, "child_count": len(self.children()),
                "changed": self._dirty, "annotations": dict(self.annotations)}


class IncompleteDocumentError(ValueError):
    pass


class Document:
    _representations = ('tree', 'asc', 'xml')
    _named_representations = ()

    def __init__(self, root: Element | None = None, *, representation='tree'):
        if representation not in self._representations:
            raise ValueError('document representation must be one of '+', '.join(self._representations))
        self._representation = representation
        self._automatic_structure = True
        self.root = root if root is not None else Element("")
        if self.root.kind or self.root.parent is not None:
            raise ValueError("document root must be an unnamed detached element")
        if self.root._document is not None:
            raise ValueError('document root is already owned; clone it first')
        self.root._document = self
        self._identity_index = None
        self.metadata: dict[str, object] = {}
        self.complete = True
        self.diagnostics: list[str] = []
        self._source_text: str | None = None
        self._source_bytes: bytes | None = None
        self._source_encoding: str = "utf-8"
        from .references import (References)
        self.references = References(self)
        self._reference_validator = None

    def _plan_field_change(self, record, name, values):
        return None

    def _prepare_value_edit(self, record, name, field, values, *, created):
        structure = (self.references.plan_collections({record: record._child_sequence()}, parents={field: record})
                     if created else None)
        projections = self.references._plan_value_changes(((field, values),), structure=structure)
        return ValueEdit(self, projections, None, record if created else None)

    def _calculation_outputs(self, slot):
        return ()

    def _plan_calculations(self, slot):
        return ()

    def _structural_calculation_slots(self, nodes):
        """Local calculation inputs whose meaning can change with ownership."""
        return ()

    def _apply_calculations(self, plans):
        pass

    def _prepare_copied_content(self, root):
        pass

    def _copy_specifications(self, root, specifications, issues):
        return specifications, issues

    def copy(self, node, *, parent=None, index=None, fields=None):
        """Copy an attached record with owned links; external targets stay shared."""
        from .record_edits import copy_record
        return copy_record(self, node, parent=parent, index=index, fields=fields)

    def remove(self, node):
        """Remove a record and its owned links, refusing external dependencies."""
        from .record_edits import remove_record
        return remove_record(self, node)

    def _apply_field_change(self, plan):
        pass

    def _field_plan_values(self, plan):
        return ()

    def _validate_reference_change(self, reference, target):
        pass

    def _prepare_reference_binding(self, reference):
        """Add domain-owned projections before a relationship is checked."""
        return reference

    def _plan_reference_outputs(self, references):
        """Prepare domain-owned collection projections in the proposed graph."""
        return ()

    def _attachment_required(self, parent, node):
        return False

    def _plan_attachment(self, parent, node, structure):
        return None

    def _apply_attachment(self, plan):
        pass

    def _validate_reference_removal(self, reference):
        pass

    def _unresolved_reference_fields(self, issue):
        """Calculated fields whose inputs constrain an unresolved selection."""
        return ()

    def _validate_unresolved_reference(self, issue):
        """Validate model constraints against the current or prospective graph."""
        pass

    def _validate_move(self, node, parent):
        pass

    def _validate_structural_references(self, references):
        pass

    def _structural_dependents(self, nodes):
        return ()

    def _reference_collection_dependencies(self, reference):
        return ()

    @property
    def representation(self):
        """Current API view, independent of input provenance or export format."""
        return self._representation

    def select(self, path: str, *, where=None) -> list[Element]:
        return self.root.select(path, where=where)

    def one(self, path: str, *, where=None) -> Element:
        return self.root.one(path, where=where)

    def find_all(self, kind: str, *, where=None) -> list[Element]:
        return self.root.find_all(kind, recursive=True, where=where)

    def rebuild_index(self) -> dict[str, Element]:
        index = {}
        pending = [self.root]
        while pending:
            node = pending.pop()
            if node.uid in index:
                raise ValueError(f"duplicate element identity: {node.uid}")
            index[node.uid] = node
            children = [item for item in node._items if isinstance(item, Element)]
            for child in children:
                if child.parent is not node:
                    raise ValueError(f"inconsistent parent for {child.uid}")
            pending.extend(reversed(children))
        return index

    def get(self, uid: str) -> Element:
        if self._identity_index is None:
            self._identity_index = self.rebuild_index()
        try:
            return self._identity_index[uid]
        except KeyError:
            raise LookupError(f"unknown element identity: {uid}") from None

    def _validate_structure(self):
        index = self.rebuild_index()
        for node in index.values():
            if node.schema is not None:
                if self.representation in self._named_representations and any(isinstance(item, Value) for item in node._items):
                    raise ValueError(f'{node.path}: unnamed values are not part of the {self.representation} record schema')
                node.schema.validate_fields(node)
                node.schema.validate_children(node)
        if self._reference_validator:
            self._reference_validator(self)
        return index

    def validate(self):
        """Audit the full tree and references without projecting output indices.

        Raises on invalid ownership, missing required fields, invalid stored types
        or unsafe references.
        Unresolved identities may remain when their guarded contents are intact.
        """
        index = self._validate_structure()
        self.references.validate()
        self._identity_index = index

    def rebuild(self, *, force=True):
        """Advanced validation plus projection of compatibility index fields."""
        index = self._validate_structure()
        self.references.synchronize(force=force)
        self._identity_index = index
        return index

    def unresolved(self) -> list[str]:
        return self.diagnostics + [f"{n.path}: {n.annotations['incomplete']}"
                                   for n in self.root.walk() if n.annotations.get("incomplete")]

    def clone(self) -> "Document":
        mapping = {}
        doc = type(self)(self.root._clone(mapping), representation=self.representation)
        doc.metadata = deepcopy(self.metadata)
        doc.complete, doc.diagnostics = self.complete, list(self.diagnostics)
        doc._source_text, doc._source_bytes = self._source_text, self._source_bytes
        doc._source_encoding = self._source_encoding
        doc._automatic_structure = False
        try:
            doc.references = self.references.clone_to(doc, mapping)
        finally:
            doc._automatic_structure = True
        doc._reference_validator = self._reference_validator
        return doc
