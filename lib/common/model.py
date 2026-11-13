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
from .schema import MISSING, _bind_validation_preview
from .validation_scope import _active as _checked_preparation
from .element_storage import FieldItems, RecordItems, _bind_model_types
from .field_edits import proposed_arguments, field_proposal, ValueEdit, _values as _prospective_values
from .structural_edits import (ordinal_override, parent_override, children_override, validate_child_change,
                               preview_structure, DetachedSnapshot, assembly,
                               _structure as _prospective_structure, _ordinals as _prospective_ordinals)


Scalar = str | int | float | Decimal | bool | None
ELEMENT_NAME = r"[A-Za-z_][A-Za-z_0-9.-]*"
_NAME = re.compile(ELEMENT_NAME + r"\Z")
_SYMBOL = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z")
_EMPTY_CHILDREN = {None: ()}


@lru_cache(maxsize=1024)
def _valid_element_name(kind):
    """Cache syntax checks, never mutable element state."""
    return _NAME.fullmatch(kind) is not None


@dataclass(frozen=True, slots=True)
class SourceSpan:
    format: str
    start: int
    end: int
    source: str | None = None


@dataclass(frozen=True, slots=True)
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
        if isinstance(value, Decimal) and not value.is_finite():
            raise ValueError("numbers must be finite")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("numbers must be finite")
        if isinstance(value, (int, float, Decimal)):
            if unit not in ("", "%"):
                raise ValueError(f"unsupported numeric unit: {unit!r}")
            return cls(value, "number", unit)
        raise TypeError(f"unsupported value: {type(value).__name__}")


class Element:
    # Most designs contain many scalar-field elements. Keep their fixed state
    # compact while retaining custom attributes and weak references.
    __slots__ = ('_uid', '_kind', '_content', '_children_cache', '_positions_cache',
                 '_schema', '_document', '_parent', '_source', '_annotations',
                 '_syntax', '_dirty_flag', '_reordered_flag', '__dict__', '__weakref__')

    def __init__(self, kind: str, *values: Scalar | float | Value, source: SourceSpan | None = None):
        if kind and not _valid_element_name(kind):
            raise ValueError(f"invalid element kind: {kind!r}")
        self._uid = None
        self._kind = kind
        self._content = [Value.of(v) for v in values]
        self._children_cache = None
        self._positions_cache = None
        self._schema = None
        self._document = None
        self._parent: Element | None = None
        self.source = source
        self._annotations: dict[str, object] | None = None
        self._syntax = None
        self._dirty = True
        self._reordered = True

    @property
    def _items(self):
        return self._content

    @_items.setter
    def _items(self, items):
        if type(self._content) in (RecordItems, FieldItems):
            self._content.replace(items)
        else:
            self._content = items

    @property
    def source(self):
        return self._content.source() if type(self._content) is FieldItems else self._source

    @source.setter
    def source(self, source):
        if type(self._content) is FieldItems:
            self._content.set_source(source)
        else:
            self._source = source

    @property
    def _dirty(self):
        if type(self._content) is FieldItems:
            return bool(self._content.record.dirty_fields & (1 << self._content.slot))
        return self._dirty_flag

    @_dirty.setter
    def _dirty(self, value):
        if type(self._content) is FieldItems:
            content, bit = self._content, 1 << self._content.slot
            content.record.dirty_fields = content.record.dirty_fields | bit if value else content.record.dirty_fields & ~bit
        else:
            self._dirty_flag = value

    @property
    def _reordered(self):
        if type(self._content) is FieldItems:
            return bool(self._content.record.reordered_fields & (1 << self._content.slot))
        return self._reordered_flag

    @_reordered.setter
    def _reordered(self, value):
        if type(self._content) is FieldItems:
            content, bit = self._content, 1 << self._content.slot
            content.record.reordered_fields = content.record.reordered_fields | bit if value else content.record.reordered_fields & ~bit
        else:
            self._reordered_flag = value

    @property
    def annotations(self) -> dict[str, object]:
        """Optional inspection/user notes, allocated only when requested."""
        if self._annotations is None:
            self._annotations = {}
            if type(self._content) is FieldItems:
                self._content.set_notes(self._annotations)
        return self._annotations

    @annotations.setter
    def annotations(self, value):
        self._annotations = value
        if type(self._content) is FieldItems:
            self._content.set_notes(value)

    @property
    def uid(self) -> str:
        if self._uid is None:
            self._uid = uuid4().hex
            if (scope := _checked_preparation.get()) is not None:
                scope.identity(self)
        if type(self._content) is FieldItems:
            self._content.remember_uid(self._uid)
        return self._uid

    @property
    def kind(self) -> str:
        return self._kind

    @kind.setter
    def kind(self, kind: str):
        if not _valid_element_name(kind):
            raise ValueError(f"invalid element kind: {kind!r}")
        if self._kind != kind:
            if type(self._content) is FieldItems:
                self._content.record.materialize(self)
            self._kind = kind
            if self._parent is not None:
                self._parent._children_cache = None
                self._parent._positions_cache = None
                if type(self._parent._content) is RecordItems:
                    self._parent._content.invalidate()
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
        content = self._content
        items = content.order if type(content) is RecordItems else content
        if len(items) == 1 and isinstance(items[0], Value):
            direct = (items[0],)
        else:
            direct = tuple(i for i in items if isinstance(i, Value))
        if self._schema is None or not self._schema.parameters:
            return direct
        named = []
        for name in self._schema.parameters:
            definition = self._schema.fields[name]
            if definition.getter is not None:
                named.append(Value.of(definition.getter(self)))
            elif (type(content) is RecordItems and _prospective_structure.get() is None
                  and _prospective_values.get() is None
                  and name in content.storage):
                named.append(content.argument(content.storage.layout.slots[name]))
            else:
                child = self.child(name)
                named.append(child.arguments[0] if child is not None else Value.of(definition.default))
        return tuple(named) + direct

    @property
    def values(self) -> tuple[Scalar, ...]:
        content = self._content
        proposed = _prospective_values.get()
        if proposed is not None and (arguments := proposed.get(self)) is not None:
            return tuple(value.value for value in arguments)
        # A preview changes particular fields, not every scalar in the model.
        # Read unaffected slots directly; parameter records still consult each
        # field's proposal before projecting their positional values.
        if type(content) is FieldItems:
            return content.values()
        if type(content) is RecordItems and _prospective_structure.get() is None:
            named = []
            for name in self._schema.parameters if self._schema is not None else ():
                definition = self._schema.fields[name]
                if definition.getter is not None:
                    named.append(Value.of(definition.getter(self)).value)
                else:
                    value = self._field_value(name, definition) if proposed else content.value(name)
                    if value is MISSING:
                        break
                    named.append(value[0] if definition.kind == 'tuple' else value)
            else:
                return tuple(named) + tuple(item.value for item in content.order if isinstance(item, Value))
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
        if (scope := _checked_preparation.get()) is not None:
            scope.touch(self)

    def _child_sequence(self, kind=None):
        """Private immutable lookup; public callers receive independent lists."""
        if _prospective_structure.get() is not None:
            prospective = children_override(self, kind)
            if prospective is not None:
                return prospective
        if type(self._content) in (RecordItems, FieldItems):
            return self._content.children(kind)
        if self._children_cache is not None:
            return self._children_cache.get(kind, ())
        return self._stored_child_sequence(kind)

    def _stored_child_sequence(self, kind=None):
        if type(self._content) in (RecordItems, FieldItems):
            return self._content.children(kind)
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
        if type(self._content) is FieldItems:
            siblings = parent._stored_child_sequence(self.kind)
            return siblings.index(self)
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
        if (scope := _checked_preparation.get()) is not None:
            scope.schema(self)
        if type(self._content) is FieldItems:
            self._content.record.materialize(self)
        if self._schema is not None:
            if self._schema.parameters != schema.parameters:
                raise ValueError('record already has an incompatible parameter schema')
            self._schema = schema
            if type(self._content) is RecordItems:
                self._content.rebind(schema)
            return self._compact_bound_fields()
        content = self._content
        items = content.order if type(content) is RecordItems else content
        raw = tuple(item for item in items if isinstance(item, Value))
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
        if type(content) is RecordItems:
            content.order = list(raw[len(schema.parameters):]) + [item for item in content.order if not isinstance(item, Value)]
        else:
            self._items = list(raw[len(schema.parameters):]) + self.children()
        self._schema = schema
        if type(content) is RecordItems and content.storage.layout.schema is not schema:
            content.rebind(schema)
        self._touch(reordered=True)
        if plan and type(content) is not RecordItems:
            owner = self._owner()
            if owner is None or not owner._automatic_structure:
                # Constructor/import binding can place named header values
                # directly into slots. Live attachment planning keeps the
                # ordinary authoring path below.
                self._compact_bound_fields()
                content = self._content
        for name, value in plan:
            if type(content) is not RecordItems or not content.import_field(name, (value,)):
                self.add(name, value)
        return self._compact_bound_fields()

    def _compact_bound_fields(self):
        """Use named value storage while keeping explicit text syntax separate."""
        if type(self._content) is not RecordItems:
            owner = self._owner()
            if (owner is None or owner.representation == 'tree'
                    or owner.representation in owner._named_representations):
                self._compact_fields(retain_debug=True)
        return self

    def _compact_fields(self, *, recursive=False, retain_debug=False):
        """Enable canonical value slots without changing the public field view."""
        if self._schema is not None and type(self._content) not in (RecordItems, FieldItems):
            self._content = RecordItems(self, self._schema, self._content, retain_debug=retain_debug)
            self._children_cache = self._positions_cache = None
            owner = self._owner()
            if owner is not None:
                owner._identity_index = None
        if recursive:
            children = (tuple(item for item in self._content.order if isinstance(item, Element))
                        if type(self._content) is RecordItems else self._child_sequence())
            for child in children:
                child._compact_fields(recursive=True, retain_debug=retain_debug)
        return self

    def _append_import(self, node):
        """Attach a fresh adapter-owned child before the import audit boundary."""
        if node._parent is not None or node._document is not None:
            raise ValueError('import construction requires a detached fresh child')
        node._parent = self
        self._content.append(node)
        self._children_cache = self._positions_cache = None
        self._dirty = self._reordered = True
        if (scope := _checked_preparation.get()) is not None:
            scope.attach(self, node)
        return node

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
        if _prospective_structure.get() is None:
            while root._parent is not None:
                root = root._parent
            return root._document
        while root.parent is not None:
            root = root.parent
        return root._document

    def __getitem__(self, name):
        if not isinstance(name, str):
            raise TypeError('field names must be strings')
        definition = self._schema.fields.get(name) if self._schema is not None else None
        if definition is not None and definition.getter is not None:
            return definition.getter(self)
        if type(self._content) is RecordItems and _prospective_structure.get() is None:
            value = self._field_value(name, definition)
            if value is not MISSING:
                return value
        child = self.child(name)
        if child is None:
            raise KeyError(name)
        if ((self._schema is not None and name in self._schema.children) or
                child._child_sequence() and not (definition is not None and definition.kind == 'tuple')):
            raise TypeError(f'{name} is a child record or collection; use child()')
        values = child.values
        return values if definition is not None and definition.kind == 'tuple' else (
            values[0] if len(values) == 1 else values)

    def _field_value(self, name, definition):
        """Read a compact field, respecting a preview of this particular slot."""
        content = self._content
        proposed = _prospective_values.get()
        if proposed:
            slot = content.storage.layout.slots.get(name)
            handle = content.handles.get(slot)
            if handle in proposed:
                arguments = proposed[handle]
                if definition is not None and definition.kind == 'tuple':
                    return tuple(argument.value for argument in arguments)
                return arguments[0].value if len(arguments) == 1 else MISSING
        value = content.value(name)
        if definition is None and isinstance(value, tuple) and len(value) == 1:
            return value[0]
        return value

    def _field_arguments(self, name):
        """Adapter read of field values without requiring an editable handle.

        Paths, structural fields and malformed records retain ordinary one()
        behavior. The direct slot path still observes prospective edits.
        """
        content = self._content
        if type(content) is RecordItems and _prospective_structure.get() is None:
            slot = content.storage.layout.slots.get(name)
            if (slot is not None and name in content.storage
                    and name not in content._owned_records()):
                value = content.value(name)
                if value is not MISSING:
                    proposed = _prospective_values.get()
                    handle = content.handles.get(slot) if proposed else None
                    if proposed and handle in proposed:
                        return proposed[handle]
                    width = len(value) if content.storage.layout.definitions[slot].kind == 'tuple' else 1
                    return tuple(content.argument(slot, index) for index in range(width))
        return self.one(name).arguments

    def get(self, name, default=None):
        try:
            return self[name]
        except KeyError:
            return default

    def in_units(self, units=None):
        """View declared lengths/areas in mm, mil or inch over these same facts."""
        from .unit_views import in_units
        return in_units(self, units)

    def __contains__(self, name):
        if not isinstance(name, str):
            return False
        if type(self._content) is RecordItems and _prospective_structure.get() is None and name in self._content.storage:
            return True
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

    def _record_children(self):
        if type(self._content) is RecordItems:
            return self._content.record_children()
        return self._child_sequence()

    def _child_kinds(self):
        return (self._content.child_kinds() if type(self._content) is RecordItems
                else (child.kind for child in self._child_sequence()))

    def _record_walk(self, *, include_self=False):
        """Adapter traversal over owned records, leaving stored scalar views lazy."""
        stack = [self] if include_self else list(reversed(self._record_children()))
        while stack:
            node = stack.pop()
            yield node
            stack.extend(reversed(node._record_children()))

    def _mark_loaded(self, *, clear_syntax=False):
        for node in self._record_walk(include_self=True):
            node._dirty = node._reordered = False
            if clear_syntax:
                node._syntax = None
            if type(node._content) is RecordItems:
                node._content.dirty_fields = node._content.reordered_fields = 0
                if clear_syntax:
                    for field in node._content.handles.values():
                        field._syntax = None

    def descendants(self, kind: str | None = None) -> list["Element"]:
        if kind is None:
            return list(self.walk())
        def children(node):
            return (tuple(node._content.search_children(kind)) if type(node._content) is RecordItems
                    else node._child_sequence())
        result, pending = [], list(reversed(children(self)))
        while pending:
            node = pending.pop()
            if node.kind == kind:
                result.append(node)
            pending.extend(reversed(children(node)))
        return result

    def select(self, path: str, *, where=None) -> list["Element"]:
        from .query import (select)
        return select(self, path, where=where)

    def one(self, path: str, *, where=None) -> "Element":
        matches = (self._child_sequence(path) if where is None and _valid_element_name(path)
                   else self.select(path, where=where))
        if len(matches) != 1:
            raise LookupError(f"expected one match for {path!r}, found {len(matches)}")
        return matches[0]

    def scalar(self, name: str, default=None, *, occurrence=0):
        definition = self._schema.fields.get(name) if self._schema is not None else None
        if occurrence == 0 and self._schema is not None:
            if definition is not None and definition.getter is not None:
                return definition.getter(self)
        if (occurrence == 0 and type(self._content) is RecordItems
                and _prospective_structure.get() is None):
            value = self._field_value(name, definition)
            if value is not MISSING:
                return value
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
        items = self._content.order if type(self._content) is RecordItems else self._items
        positions = [i for i, item in enumerate(items) if isinstance(item, Value)]
        position = positions[index]
        replacement = Value.of(value)
        previous = items[position]
        if ((previous.value, previous.kind, previous.unit) != (replacement.value, replacement.kind, replacement.unit)
                or isinstance(value, Value) and previous != replacement):
            items[position] = replacement
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
            content = self._content
            if type(content) is RecordItems:
                # Parameters already updated their authoritative slots. Only
                # extra adapter arguments change this mixed-content order;
                # rebuilding it through children() would expand and recopy
                # every otherwise untouched field in the record.
                extra = list(replacements[count:])
                if extra or any(isinstance(item, Value) for item in content.order):
                    content.order = extra + [item for item in content.order if not isinstance(item, Value)]
            else:
                self._items = list(replacements[count:]) + self.children()
            self._touch(reordered=True)
            return self
        replacements = [Value.of(v) for v in values]
        items = self._content.order if type(self._content) is RecordItems else self._items
        positions = [i for i, item in enumerate(items) if isinstance(item, Value)]
        if len(positions) == len(replacements):
            changed = False
            for i, value, supplied in zip(positions, replacements, values):
                old = items[i]
                if ((old.value, old.kind, old.unit) != (value.value, value.kind, value.unit)
                        or isinstance(supplied, Value) and old != value):
                    items[i] = value
                    changed = True
            if changed:
                self._touch()
        else:
            if type(self._content) is RecordItems:
                self._content.order = replacements + [item for item in items if not isinstance(item, Value)]
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
        if (scope := _checked_preparation.get()) is not None:
            scope.attach(self, node)
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
        if (scope := _checked_preparation.get()) is not None:
            scope.attach(parent, self, incoming=owner is not destination)
        for document, plan in plans:
            document.references.apply_value_change(plan)
            document.references.refresh_structure(moved)
            document.references.finish_structure(changes, removed=moved if document is owner and owner is not destination else ())
        return self

    def _audit_owned_content(self):
        """Read actual owned content, independently of warmed lookup caches."""
        self._children_cache = self._positions_cache = None
        content = self._content
        if type(content) is RecordItems:
            content.validate()
            return content.record_children()
        return tuple(item for item in content if isinstance(item, Element))

    def clone(self) -> "Element":
        """Copy content and formatting with fresh identities and no shared children."""
        return self._clone()

    def _clone(self, mapping=None):
        """Collect document ownership mappings during the copy traversal."""
        result = Element(self.kind, source=self.source)
        result._schema = self._schema
        result._dirty, result._reordered = self._dirty, self._reordered
        if mapping is not None:
            mapping[self] = result
        if self._annotations:
            result._annotations = deepcopy(self._annotations)
        if type(self._content) is RecordItems:
            result._content = self._content.clone_to(result, mapping)
            return result
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
                "changed": self._dirty, "annotations": dict(self._annotations or ())}


class IncompleteDocumentError(ValueError):
    pass


class Document:
    _representations = ('tree', 'asc', 'xml')
    _named_representations = ()

    def in_units(self, units=None):
        """View this editable document in selected natural length units."""
        from .unit_views import in_units
        return in_units(self, units)

    def _record_definition(self, node):
        """Resolve a prospective owned record; domains supply their catalogue."""
        return node.schema

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

    def _field_arguments(self, path):
        return self.root._field_arguments(path)

    def find_all(self, kind: str, *, where=None) -> list[Element]:
        return self.root.find_all(kind, recursive=True, where=where)

    def rebuild_index(self) -> dict[str, Element]:
        index = {}
        pending = [self.root]
        while pending:
            node = pending.pop()
            if type(node._content) is RecordItems:
                node._content.validate()
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
        if self._identity_index is None or uid not in self._identity_index:
            self._identity_index = self._observed_index()
        try:
            result = self._identity_index[uid]
        except KeyError:
            raise LookupError(f"unknown element identity: {uid}") from None
        return result.record.field(result.slot) if type(result) is FieldItems else result

    def _observed_index(self):
        """Index already observed IDs without generating IDs or retaining leaf views."""
        index = {}
        for node in self._audit_nodes():
            if node._uid is not None:
                index[node._uid] = node
            if type(node._content) is RecordItems:
                for slot, uid in node._content.identities.items():
                    index[uid] = FieldItems(node._content, slot)
        return index

    def _audit_nodes(self):
        """Inspect actual ownership and known identities without creating field IDs."""
        pending, seen, identities = [self.root], set(), set()
        while pending:
            node = pending.pop()
            if id(node) in seen:
                raise ValueError('an element occurs more than once in the document')
            seen.add(id(node))
            if node._uid is not None:
                if node._uid in identities:
                    raise ValueError(f'duplicate element identity: {node._uid}')
                identities.add(node._uid)
            children = node._audit_owned_content()
            content = node._content
            if type(content) is RecordItems:
                for uid in content.identities.values():
                    if uid in identities:
                        raise ValueError(f'duplicate element identity: {uid}')
                    identities.add(uid)
            for child in children:
                if child.parent is not node:
                    raise ValueError(f'inconsistent parent for {child.uid}')
            yield node
            pending.extend(reversed(children))

    def _validate_structure(self, *, materialize=False):
        index = self.rebuild_index() if materialize else None
        for node in index.values() if index is not None else self._audit_nodes():
            self._validate_record(node)
        if self._reference_validator:
            self._reference_validator(self)
        return index

    def _validate_record(self, node):
        if node.schema is not None:
            content = node._content.order if type(node._content) is RecordItems else node._content
            if self.representation in self._named_representations and any(isinstance(item, Value) for item in content):
                raise ValueError(f'{node.path}: unnamed values are not part of the {self.representation} record schema')
            node.schema.validate_fields(node)
            node.schema.validate_children(node)

    def validate(self):
        """Audit the full tree and references without projecting output indices.

        Raises on invalid ownership, missing required fields, invalid stored types
        or unsafe references.
        Unresolved identities may remain when their guarded contents are intact.
        """
        self._validate_structure()
        self.references.validate()
        self._identity_index = None

    def _synchronize(self, *, force=True):
        """Adapter boundary: audit and project without building an inspection index."""
        self._validate_structure()
        self.references.synchronize(force=force)
        self._identity_index = None

    def rebuild(self, *, force=True):
        """Advanced validation plus projection of compatibility index fields."""
        index = self._validate_structure(materialize=True)
        self.references.synchronize(force=force)
        self._identity_index = index
        return index

    def unresolved(self) -> list[str]:
        return self.diagnostics + [f"{n.path}: {n._annotations['incomplete']}"
                                   for n in self.root.walk() if n._annotations and n._annotations.get("incomplete")]

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


_bind_model_types(Element, Value)
_bind_validation_preview(
    lambda: (_prospective_values.get() is not None or _prospective_structure.get() is not None
             or _prospective_ordinals.get() is not None),
    structure=lambda: (_prospective_structure.get() is not None or _prospective_ordinals.get() is not None),
    values=_prospective_values.get)
