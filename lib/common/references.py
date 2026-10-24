"""Identity-based links with incrementally maintained value projections.

A target can supply several serialized indices. For example, one pin supplies
its own index and the index of its containing component. The graph itself knows
nothing about a particular file format or electrical model.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from contextlib import contextmanager
from collections import deque
from uuid import uuid4

from .model import (Element, Value)
from .structural_edits import preview_structure, validate_child_change
from .computed_dependencies import ComputedDependencies
from .reference_edits import pending_changes, preview_references


class ReferenceError(ValueError):
    pass


@dataclass(frozen=True)
class Index:
    field: Element
    argument: int = 0
    ancestor: int = 0
    offset: int = 0


@dataclass(frozen=True)
class Key:
    """Project a target's named key instead of its position in an array."""
    field: Element
    name: str = 'Id'
    argument: int = 0
    ancestor: int = 0


@dataclass(frozen=True)
class Property:
    """Project a target's field/tuple value without requiring a unique key.

    name=None selects the target's own arguments. This lets one identity keep
    a redundant name synchronized alongside its positional index.
    """
    field: Element
    name: str | None = None
    argument: int = 0
    ancestor: int = 0
    target_argument: int = 0


@dataclass(frozen=True)
class Guard:
    field: Element
    values: tuple


@dataclass(frozen=True)
class OrdinalGuard:
    """Require a member's current position to remain within an inclusive limit."""
    field: Element
    member: Element

    @property
    def values(self):
        return (True,)


@dataclass(frozen=True)
class Segment:
    """Two adjacent elements whose order may change when a route is reversed."""
    start: Element
    end: Element


@dataclass(frozen=True)
class Reference:
    uid: str
    source: Element
    target: Element | Segment
    role: str
    indices: tuple[Index | Key | Property, ...]
    guards: tuple[Guard | OrdinalGuard, ...] = ()


@dataclass(frozen=True)
class UnresolvedReference:
    source: Element
    message: str
    indices: tuple[Index | Key | Property, ...]
    collections: tuple[Element, ...] | None = None
    guards: tuple[Guard | OrdinalGuard, ...] = ()


@dataclass
class _Binding:
    reference: Reference
    values: tuple[Value, ...]
    positions: tuple[object, ...]
    domains: tuple[tuple[str, ...], ...]
    sequence: int = 0


@dataclass
class _ProjectionPlan:
    updates: tuple
    values: dict
    calculations: tuple = ()

    def __iter__(self):
        return iter(self.updates)


@dataclass(frozen=True)
class _NamedArgument:
    name: str
    argument: int


@dataclass
class _Additions:
    bindings: tuple
    projections: _ProjectionPlan


def _within(node, ancestor):
    while node is not None:
        if node is ancestor:
            return True
        node = node.parent
    return False


class References:
    def __init__(self, document):
        self.document = document
        self._bindings: dict[str, _Binding] = {}
        self._incoming = {}
        self._outgoing = {}
        self._next_sequence = 0
        self._value_consumers = {}
        self._value_slots = {}
        self._key_scopes = {}
        self._key_reference_scopes = {}
        self._guard_consumers = {}
        self._guard_slots = {}
        self._issue_guard_consumers = {}
        self._issue_guard_slots = {}
        self._issues_by_node = {}
        self._issue_content = {}
        self._issue_sequence = {}
        self._next_issue_sequence = 0
        self._slots: dict[tuple[Element, int], str] = {}
        self.issues: list[UnresolvedReference] = []
        self._unresolved_values = {}
        self._watched = {}
        self._binding_orders = None
        self._pending_index_collections = set()
        self._collection_users = {}
        self._reference_collections = {}
        self._computed = ComputedDependencies()
        self._content_users = {}
        self._reference_content = {}
        self._key_collection_users = {}

    @contextmanager
    def binding_batch(self):
        """Share lookup tables while importing bindings into an unchanged tree.

        Bindings in this scope must use preserve=True. No document fields or
        collections may be changed until the batch has finished.
        """
        if self._binding_orders is not None:
            yield
            return
        self._binding_orders = {}
        try:
            yield
        finally:
            self._binding_orders = None

    def __len__(self):
        changes = pending_changes(self)
        if changes is None:
            return len(self._bindings)
        return len(self._bindings) + sum(
            int(reference is not None and uid not in self._bindings) -
            int(reference is None and uid in self._bindings) for uid, reference in changes.items())

    def __iter__(self):
        return iter(self._visible(self._bindings))

    def _visible(self, uids):
        changes = pending_changes(self)
        if changes is None:
            return (self._bindings[uid].reference for uid in uids)
        return (reference for reference in (
            *(self._bindings[uid].reference for uid in uids if uid not in changes),
            *changes.values()) if reference is not None)

    def _sequence(self, reference):
        binding = self._bindings.get(reference.uid)
        return binding.sequence if binding is not None else self._next_sequence

    def get(self, uid):
        changes = pending_changes(self)
        if changes is not None and uid in changes:
            if changes[uid] is None:
                raise LookupError(f'unknown reference identity: {uid}')
            return changes[uid]
        try:
            return self._bindings[uid].reference
        except KeyError:
            raise LookupError(f'unknown reference identity: {uid}') from None

    def incoming(self, target, *, role=None):
        return [reference for reference in sorted(self._visible(self._incoming.get(target, ())), key=self._sequence)
                if (reference.target is target or isinstance(reference.target, Segment) and
                    target in (reference.target.start, reference.target.end)) and
                (role is None or reference.role == role)]

    def outgoing(self, source, *, role=None):
        return [reference for reference in sorted(self._visible(self._outgoing.get(source, ())), key=self._sequence)
                if reference.source is source and (role is None or reference.role == role)]

    @staticmethod
    def _targets(reference):
        target = reference.target
        if isinstance(target, Segment):
            return tuple(dict.fromkeys((target, target.start, target.end)))
        return (target,)

    @staticmethod
    def _unindex(index, owner, uid):
        bucket = index[owner]
        del bucket[uid]
        if not bucket:
            del index[owner]

    def _item_dependencies(self, reference, item):
        if not isinstance(item, (Property, Key)):
            return ()
        anchors = ((reference.target.start, reference.target.end)
                   if isinstance(reference.target, Segment) else (reference.target,))
        slots = set()
        for target in anchors:
            for _ in range(item.ancestor):
                target = target.parent
            owner, argument = self._property_source(target, item.name,
                item.target_argument if isinstance(item, Property) else 0)
            if owner is not None:
                slots.add(self._source_slot(owner, argument))
        return slots

    @staticmethod
    def _property_source(target, name, argument):
        if name is None:
            return target, argument
        schema = target.schema
        definition = schema.fields.get(name) if schema is not None else None
        if definition is not None and definition.getter is not None:
            if name in schema.parameters:
                return (target, schema.parameters.index(name)) if argument == 0 else (None, None)
            return target, _NamedArgument(name, argument)
        fields = target.children(name)
        return (fields[0], argument) if len(fields) == 1 else (None, None)

    @staticmethod
    def _source_slot(owner, argument):
        return (owner, argument) if isinstance(argument, _NamedArgument) else owner._argument_owner(argument)

    def _dependency_slots(self, reference):
        return {slot for item in reference.indices for slot in self._item_dependencies(reference, item)}

    def _validate_copy_cycles(self, reference, *, companions=()):
        proposed = {}
        outputs = set()
        replacements = {item.uid: item for item in (reference, *companions)}
        for current in replacements.values():
            for item in current.indices:
                output = item.field._argument_owner(item.argument)
                for dependency in self._item_dependencies(current, item):
                    proposed.setdefault(dependency, set()).add(output)
                    outputs.add(output)
        for origin in outputs:
            pending, visited = [origin], set()
            while pending:
                slot = pending.pop()
                following = set(proposed.get(slot, ())) | set(self.document._calculation_outputs(slot))
                for uid in self._value_consumers.get(slot, ()):
                    if uid in replacements:
                        continue
                    current = self._bindings[uid].reference
                    following.update(item.field._argument_owner(item.argument) for item in current.indices
                                     if slot in self._item_dependencies(current, item))
                if origin in following:
                    raise ReferenceError('property/key copies cannot form a cycle')
                for successor in following - visited:
                    visited.add(successor)
                    pending.append(successor)

    def _index_values(self, reference):
        slots = self._dependency_slots(reference)
        if slots:
            self._value_slots[reference.uid] = slots
            for slot in slots:
                self._value_consumers.setdefault(slot, {})[reference.uid] = None
        scopes = set()
        anchors = ((reference.target.start, reference.target.end)
                   if isinstance(reference.target, Segment) else (reference.target,))
        for item in reference.indices:
            if isinstance(item, Key):
                for target in anchors:
                    for _ in range(item.ancestor):
                        target = target.parent
                    scopes.add((target.parent, target.kind, item.name))
        if scopes:
            self._key_reference_scopes[reference.uid] = scopes
            for scope in scopes:
                self._key_scopes.setdefault(scope, {})[reference.uid] = None
            for collection in {scope[:2] for scope in scopes}:
                self._key_collection_users.setdefault(collection, {})[reference.uid] = None
        self._refresh_computed(reference)

    def _unindex_values(self, reference):
        for slot in self._value_slots.pop(reference.uid, ()):
            self._unindex(self._value_consumers, slot, reference.uid)
        scopes = self._key_reference_scopes.pop(reference.uid, ())
        for scope in scopes:
            self._unindex(self._key_scopes, scope, reference.uid)
        for collection in {scope[:2] for scope in scopes}:
            self._unindex(self._key_collection_users, collection, reference.uid)
        self._computed.discard(reference.uid)

    @staticmethod
    def _calculated_parameters(owner):
        if owner is not None and owner.schema is not None:
            for name in owner.schema.parameters:
                definition = owner.schema.fields[name]
                if definition.getter is not None:
                    yield owner, definition

    def _calculated_fields(self, reference):
        for guard in reference.guards:
            yield from self._calculated_parameters(guard.field)
        if isinstance(reference, UnresolvedReference):
            return
        for item in reference.indices:
            if not isinstance(item, (Property, Key)):
                continue
            anchors = ((reference.target.start, reference.target.end)
                       if isinstance(reference.target, Segment) else (reference.target,))
            for target in anchors:
                for _ in range(item.ancestor):
                    target = target.parent
                owner, argument = self._property_source(target, item.name,
                    item.target_argument if isinstance(item, Property) else 0)
                if owner is not None and owner.schema is not None and isinstance(argument, _NamedArgument):
                    yield owner, owner.schema.fields[argument.name]
                elif owner is not None and owner.schema is not None and argument < len(owner.schema.parameters):
                    definition = owner.schema.fields[owner.schema.parameters[argument]]
                    if definition.getter is not None:
                        yield owner, definition

    def _refresh_computed(self, reference):
        key = reference if isinstance(reference, UnresolvedReference) else reference.uid
        self._computed.update(key, self._calculated_fields(reference),
                              ordinals=(guard.member for guard in reference.guards if isinstance(guard, OrdinalGuard)))

    def _track_collections(self, reference):
        collections = set(self._index_collections(reference))
        if isinstance(reference.target, Segment):
            collections.add((reference.target.start.parent, reference.target.start.kind))
        if collections:
            self._reference_collections[reference.uid] = collections
            for collection in collections:
                self._collection_users.setdefault(collection, {})[reference.uid] = None
        content = {reference.source, *self._targets(reference),
                   *(item.field for item in reference.indices), *(guard.field for guard in reference.guards),
                   *(owner for owner, _ in self._dependency_slots(reference))}
        self._reference_content[reference.uid] = content
        for node in content:
            self._content_users.setdefault(node, {})[reference.uid] = None

    def _untrack_collections(self, reference):
        for collection in self._reference_collections.pop(reference.uid, ()):
            self._unindex(self._collection_users, collection, reference.uid)
        for node in self._reference_content.pop(reference.uid, ()):
            self._unindex(self._content_users, node, reference.uid)

    def _scopes_for_slot(self, slot):
        field = slot[0]
        while field.parent is not None and field.parent.parent is not None:
            record = field.parent
            scope = record.parent, record.kind, field.kind
            if scope in self._key_scopes:
                yield scope
            field = record

    def value_consumers(self, field, argument=0):
        return tuple(self._bindings[uid].reference
                     for uid in self._value_consumers.get(field._argument_owner(argument), ()))

    def property_consumers(self, target, name, argument=0):
        owner, argument = self._property_source(target, name, argument)
        if owner is None:
            return ()
        return tuple(self._bindings[uid].reference
                     for uid in self._value_consumers.get(self._source_slot(owner, argument), ()))

    @staticmethod
    def _guard_dependencies(guards):
        return {(guard.field, None) for guard in guards} | {
            guard.field._argument_owner(index) for guard in guards
            for index in range(len(guard.field.arguments))}

    def _index_guards(self, reference):
        slots = self._guard_dependencies(reference.guards)
        if slots:
            self._guard_slots[reference.uid] = slots
            for slot in slots:
                self._guard_consumers.setdefault(slot, {})[reference.uid] = None

    def _unindex_guards(self, reference):
        for slot in self._guard_slots.pop(reference.uid, ()):
            self._unindex(self._guard_consumers, slot, reference.uid)

    def guard_consumers(self, field, argument=0):
        uids = dict.fromkeys((*self._guard_consumers.get(field._argument_owner(argument), ()),
                              *self._guard_consumers.get((field, None), ())))
        return tuple(self._bindings[uid].reference for uid in uids)

    def unresolved_guard_consumers(self, field, argument=0):
        return tuple(dict.fromkeys((*self._issue_guard_consumers.get(field._argument_owner(argument), ()),
                                    *self._issue_guard_consumers.get((field, None), ()))))

    def _validate_guards(self, overrides, *, excluded=(), excluded_issues=()):
        affected = {uid for slot in overrides for uid in self._guard_consumers.get(slot, ())}
        for uid in affected.difference(excluded):
            self._validate_reference_guards(self._bindings[uid].reference, overrides)
        issues = {issue for slot in overrides for issue in self._issue_guard_consumers.get(slot, ())}
        for issue in issues.difference(excluded_issues):
            self._validate_reference_guards(issue, overrides)

    @staticmethod
    def _validate_reference_guards(reference, overrides):
        for guard in reference.guards:
            if not _within(guard.field, reference.source):
                raise ReferenceError('reference guard is detached from its source')
            values = tuple(overrides.get(guard.field._argument_owner(index), value).value
                           for index, value in enumerate(guard.field.arguments))
            if isinstance(guard, OrdinalGuard):
                if not _within(guard.member, reference.source):
                    raise ReferenceError('reference guard member is detached from its source')
                if len(values) != 1 or isinstance(values[0], bool) or not isinstance(values[0], (int, float, Decimal)) or int(values[0]) != values[0]:
                    raise ReferenceError('ordinal guard requires an integer limit')
                values = (guard.member._ordinal() <= values[0],)
            if values != guard.values or any(isinstance(new, bool) != isinstance(old, bool)
                                            for new, old in zip(values, guard.values)):
                raise ReferenceError('reference mode is in use; discard or replace its relationship before editing')

    @staticmethod
    def _same_value(first, second):
        return (first.kind, first.value, first.unit) == (second.kind, second.value, second.unit)

    @staticmethod
    def _projected_value(item, position, domain, *, source=None):
        kind, unit = (domain[-2], domain[-1]) if isinstance(item, Property) else (
            'string' if isinstance(position, str) else 'number', '')
        return Value(position, kind, unit, source=source)

    def _validate_projected_values(self, overrides):
        for (owner, index), value in overrides.items():
            schema = owner.schema
            if schema is not None and index < len(schema.parameters):
                definition = schema.fields[schema.parameters[index]]
                if definition.getter is not None:
                    if not self._same_value(owner.arguments[index], value):
                        raise ReferenceError('a calculated value cannot be projected independently')
                    continue
            parent_schema = owner.parent.schema if owner.parent is not None else None
            definition = parent_schema.fields.get(owner.kind) if parent_schema is not None else None
            if definition is None or definition.getter is not None:
                continue
            if definition.kind == 'tuple':
                values = tuple(overrides.get(owner._argument_owner(i), old).value
                               for i, old in enumerate(owner.arguments))
                definition.validate(values)
            elif index == 0 and len(owner.arguments) == 1:
                definition.validate(value.value)

    def plan_value_change(self, field, values):
        return self.plan_value_changes(((field, values),))

    def plan_value_changes(self, changes):
        """Preflight roots and all dependent copies without changing data."""
        return self._plan_value_changes(changes)

    def _plan_value_changes(self, changes, *, structure=None):
        overrides = {}
        for field, values in changes:
            if field is None:
                continue
            previous = field._stored_arguments()
            if len(values) != len(previous) and (
                    self.guard_consumers(field) or self.unresolved_guard_consumers(field) or any(
                    self._value_consumers.get(field._argument_owner(index)) for index in range(len(previous)))):
                raise ReferenceError('referenced field arity cannot change')
            overrides.update((field._argument_owner(index), value) for index, value in enumerate(values))
        requested = dict(overrides)
        selections, seeds = None, ()
        if structure is not None:
            overrides = {**structure.values, **overrides}
            selections = {binding.reference.uid: selected for binding, _, selected in structure}
            seeds = selections
        plan = self._plan_value_overrides(overrides, index_selection=selections, seeds=seeds)
        if structure is not None:
            plan.calculations = tuple({**dict(structure.calculations), **dict(plan.calculations)}.items())
        # Calculated roots must agree with managed copies after the complete
        # dependency graph has settled, including intermediate copies.
        self._validate_requested_values(requested, plan)
        return plan

    def _validate_requested_values(self, requested, plan, *, additions=()):
        extra_slots = {item.field._argument_owner(item.argument): binding
                       for binding in additions for item in binding.reference.indices}
        orders = {}
        for slot, value in requested.items():
            binding = extra_slots.get(slot)
            uid = self._slots.get(slot)
            if binding is None and uid is None:
                continue
            binding = binding if binding is not None else self._bindings[uid]
            positions, domains = self._positions(binding.reference, orders, overrides=plan.values)
            for item, position, domain in zip(binding.reference.indices, positions, domains):
                if item.field._argument_owner(item.argument) == slot:
                    if not self._same_value(value, self._projected_value(item, position, domain)):
                        raise ReferenceError('a managed projection cannot be changed independently')

    def _plan_value_overrides(self, overrides, *, extra=None, index_selection=None, force=False,
                              all_bindings=False, seeds=(), excluded=(), excluded_issues=()):
        pending = deque()
        queued = set()
        extras = {} if extra is None else ({extra.reference.uid: extra} if isinstance(extra, _Binding) else
                                           {binding.reference.uid: binding for binding in extra})
        extra_dependencies = {}
        for uid, binding in extras.items():
            for slot in self._dependency_slots(binding.reference):
                extra_dependencies.setdefault(slot, set()).add(uid)

        calculations, calculated_values = {}, {}
        calculation_queue, scheduled_calculations = deque(), set()

        def calculation_cycle(origin):
            pending_slots, states = [(origin, False)], {}
            while pending_slots:
                slot, finished = pending_slots.pop()
                if finished:
                    states[slot] = 2
                    continue
                if states.get(slot) == 1:
                    raise ReferenceError('property/key copies and calculations cannot form a cycle')
                if states.get(slot) == 2:
                    continue
                states[slot] = 1
                pending_slots.append((slot, True))
                successors = set(self.document._calculation_outputs(slot))
                consumers = set(self._value_consumers.get(slot, ())) - extras.keys() - set(excluded)
                consumers.update(extra_dependencies.get(slot, ()))
                for uid in consumers:
                    current = (extras[uid] if uid in extras else self._bindings[uid]).reference
                    successors.update(item.field._argument_owner(item.argument) for item in current.indices
                                      if slot in self._item_dependencies(current, item))
                pending_slots.extend((successor, False) for successor in successors)

        def schedule(slot):
            consumers = set(self._value_consumers.get(slot, ()))
            consumers.difference_update(extras)
            consumers.update(extra_dependencies.get(slot, ()))
            for scope in self._scopes_for_slot(slot):
                consumers.update(self._key_scopes[scope])
            for uid in consumers:
                if uid not in queued and uid not in excluded:
                    pending.append(uid)
                    queued.add(uid)
            if self.document._automatic_structure and slot not in scheduled_calculations:
                calculation_queue.append(slot)
                scheduled_calculations.add(slot)

        pending.extend(extras)
        queued.update(extras)
        if all_bindings:
            pending.extend(uid for uid in self._bindings if uid not in excluded and uid not in extras)
            queued.update(pending)
        for uid in seeds:
            if uid not in queued and uid not in excluded:
                pending.append(uid)
                queued.add(uid)
        for slot in overrides:
            schedule(slot)
        plans = {}
        from .field_edits import preview_slots
        while pending or calculation_queue:
            if calculation_queue:
                slot = calculation_queue.popleft()
                scheduled_calculations.remove(slot)
                with preview_slots(overrides):
                    outputs = self.document._calculation_outputs(slot)
                    if outputs:
                        calculation_cycle(slot)
                    derived = self.document._plan_calculations(slot)
                for key, plan, changes in derived:
                    calculations[key] = plan
                    for field, values in changes:
                        for index, value in enumerate(values):
                            output = field._argument_owner(index)
                            calculated_values[output] = value
                            previous = overrides.get(output, field.arguments[index])
                            if not self._same_value(previous, value):
                                overrides[output] = value
                                schedule(output)
                continue
            uid = pending.popleft()
            queued.remove(uid)
            binding = extras[uid] if uid in extras else self._bindings[uid]
            self._check(binding.reference)
            positions, domains = self._positions(binding.reference, {}, overrides=overrides, check_keys=False)
            if domains != binding.domains:
                raise ReferenceError('edited property has an incompatible type or scope')
            if uid in extras:
                selected = set(range(len(binding.reference.indices)))
            else:
                selected = {i for i, item in enumerate(binding.reference.indices)
                            if isinstance(item, (Property, Key)) and
                            (index_selection is None or force or positions[i] != binding.positions[i])}
                if index_selection is not None:
                    selected.update(index_selection.get(uid, ()))
            positions = tuple(value if i in selected else binding.positions[i]
                              for i, value in enumerate(positions))
            plans[uid] = binding, positions, selected
            for ordinal in selected:
                item = binding.reference.indices[ordinal]
                slot = item.field._argument_owner(item.argument)
                value = self._projected_value(item, positions[ordinal], domains[ordinal])
                previous = overrides[slot] if slot in overrides else slot[0].arguments[slot[1]]
                if not self._same_value(previous, value):
                    overrides[slot] = value
                    schedule(slot)
        # Check collective constraints after every copy has its final value;
        # an intermediate cache state can temporarily contain duplicate keys.
        orders = {}
        for binding, _, _ in plans.values():
            self._positions(binding.reference, orders, overrides=overrides)
        self._validate_guards(overrides, excluded=set(excluded) | extras.keys(), excluded_issues=excluded_issues)
        for binding in extras.values():
            self._validate_reference_guards(binding.reference, overrides)
        self._validate_projected_values(overrides)
        plan = _ProjectionPlan(tuple(plans.values()), overrides, tuple(calculations.items()))
        self._validate_requested_values(calculated_values, plan, additions=extras.values())
        return plan

    def _plan_reference_changes(self, changes, *, extra=None, structure=None, excluded_issues=()):
        users = set()
        for uid, replacement in changes.items():
            if uid in self._bindings:
                users.update(self._computed.relationship_users(self._bindings[uid].reference))
            if replacement is not None:
                users.update(self._computed.relationship_users(replacement))
        issues = {user for user in users if isinstance(user, UnresolvedReference)}
        users.difference_update(issues)
        excluded = {uid for uid, replacement in changes.items() if replacement is None}
        overrides, selections = {}, None
        if structure is not None:
            overrides.update(structure.values)
            selections = {}
            for binding, _, selected in structure:
                users.add(binding.reference.uid)
                selections[binding.reference.uid] = selected
        with preview_references(self, changes):
            for issue in issues.difference(excluded_issues):
                self._validate_reference_guards(issue, {})
            plan = self._plan_value_overrides(overrides, extra=extra, seeds=users, excluded=excluded,
                                              index_selection=selections, excluded_issues=excluded_issues)
            if structure is not None:
                plan.calculations = tuple({**dict(structure.calculations), **dict(plan.calculations)}.items())
            self._validate_managed_values(plan)
        return plan

    def apply_value_change(self, plan):
        for binding, positions, selected in plan:
            self._write(binding, positions, selected=selected)
            self._refresh_computed(binding.reference)
        if isinstance(plan, _ProjectionPlan) and plan.calculations:
            self.document._apply_calculations(tuple(value for _, value in plan.calculations))

    def manages(self, field, argument=0):
        return field._argument_owner(argument) in self._slots

    def unresolved_slot(self, field, argument=0):
        return field._argument_owner(argument) in self._unresolved_values

    def note(self, source, message, *indices, collections=None, guards=()):
        if collections is not None:
            collections = tuple(dict.fromkeys(collections))
            if any(not isinstance(parent, Element) or not _within(parent, self.document.root) for parent in collections):
                raise ReferenceError('unresolved reference scope is outside this document')
        issue = UnresolvedReference(source, message, tuple(indices), collections, tuple(guards))
        if any(not _within(guard.field, source) for guard in issue.guards):
            raise ReferenceError('unresolved reference guard is outside its source')
        self._validate_reference_guards(issue, {})
        if issue in self.issues:
            return self.issues[self.issues.index(issue)]
        # A newly introduced unresolved link guards the current collection
        # state. Earlier edits to an unguarded collection remain valid. Keep
        # snapshots already protected by another issue, including failed edits.
        global_scope = any(issue.collections is None for issue in self.issues)
        protected = {parent for issue in self.issues for parent in issue.collections or ()}
        parents = tuple(self._watched) if collections is None else collections
        for parent in parents:
            if global_scope or parent in protected:
                self.watch(parent)
            else:
                self._watched[parent] = tuple(parent.children())
        self.issues.append(issue)
        content = {source, *(item.field for item in indices), *(guard.field for guard in guards),
                   *(guard.member for guard in guards if isinstance(guard, OrdinalGuard)), *(collections or ())}
        self._issue_content[issue] = content
        self._issue_sequence[issue] = self._next_issue_sequence
        self._next_issue_sequence += 1
        for node in content:
            self._issues_by_node.setdefault(node, {})[issue] = None
        slots = self._guard_dependencies(issue.guards)
        if slots:
            self._issue_guard_slots[issue] = slots
            for slot in slots:
                self._issue_guard_consumers.setdefault(slot, {})[issue] = None
        for item in indices:
            self._unresolved_values[item.field._argument_owner(item.argument)] = item.field.arguments[item.argument]
        self._refresh_computed(issue)
        return issue

    def discard_issue(self, issue):
        """Explicitly stop tracking an unresolved link, for deletion/replacement."""
        if issue not in self.issues:
            raise LookupError('unresolved reference is not registered here')
        self.issues.remove(issue)
        for node in self._issue_content.pop(issue, ()):
            self._unindex(self._issues_by_node, node, issue)
        self._issue_sequence.pop(issue, None)
        self._computed.discard(issue)
        for slot in self._issue_guard_slots.pop(issue, ()):
            self._unindex(self._issue_guard_consumers, slot, issue)
        remaining = {item.field._argument_owner(item.argument) for other in self.issues for item in other.indices}
        for item in issue.indices:
            slot = item.field._argument_owner(item.argument)
            if slot not in remaining:
                self._unresolved_values.pop(slot, None)

    def watch(self, collection):
        self._watched.setdefault(collection, tuple(collection.children()))

    def _check_collection_changes(self, collections, *, excluded_issues=()):
        """Preflight a structural edit before detaching any records."""
        changed = set(collections)
        if changed and any(issue.collections is None or changed.intersection(issue.collections)
                           for issue in self.issues if issue not in excluded_issues):
            raise ReferenceError('unresolved references prevent changing these collections')

    def plan_reorder(self, parent, children):
        """Preflight only references affected by a same-parent reorder."""
        return self.plan_collections({parent: tuple(children)})

    def collection_requires_plan(self, parent, kind):
        collection = parent, kind
        return bool(self.issues or self._collection_users.get(collection) or
                    self._computed.collection_users(*collection) or self._key_collection_users.get(collection))

    def check_removal(self, node, *, excluding=()):
        """Refuse dangling links, including fields owned by a broader source."""
        removed = set(node.walk(include_self=True))
        if any(set(self._content_users.get(child, ())).difference(excluding) or
               set(self._computed.node_users(child)).difference(excluding) for child in removed):
            raise ReferenceError('referenced content cannot be removed; discard or retarget its relationships first')
        if any(issue.source in removed or any(item.field in removed for item in issue.indices) or
                any(guard.field in removed for guard in issue.guards) or
                any(collection in removed for collection in issue.collections or ())
                for issue in self.issues if issue not in excluding):
            raise ReferenceError('unresolved reference content cannot be removed; discard its relationship first')
        return removed

    def finish_structure(self, parents, *, removed=()):
        """Release stale order snapshots once an authoring edit has committed."""
        if removed:
            removed = set(removed)
        for node in removed:
            self._watched.pop(node, None)
        if removed:
            self._pending_index_collections = {collection for collection in self._pending_index_collections
                                               if collection[0] not in removed}
        for parent in parents:
            if parent in self._watched:
                self._watched[parent] = parent._child_sequence()

    def plan_collections(self, children_by_parent, *, parents=None, moved=(), excluded=(), excluded_issues=()):
        """Plan projections against a prospective tree, leaving the live tree intact."""
        self._check_collection_changes(children_by_parent, excluded_issues=excluded_issues)
        ordinals, changed = {}, set()
        for parent, children in children_by_parent.items():
            counts = {}
            kinds = {node.kind for node in parent._stored_child_sequence()} | {node.kind for node in children}
            for kind in kinds:
                if parent._stored_child_sequence(kind) != tuple(node for node in children if node.kind == kind):
                    changed.add((parent, kind))
            for node in children:
                position = counts.get(node.kind, 0)
                counts[node.kind] = position + 1
                ordinals[node] = position
        users = set()
        for node in moved:
            users.update(self._content_users.get(node, ()))
        users.update(reference.uid for reference in self.document._structural_dependents(moved))
        moved_users = set(users)
        for collection in changed:
            users.update(self._collection_users.get(collection, ()))
            users.update(self._key_collection_users.get(collection, ()))
            users.update(self._computed.collection_users(*collection))
        for node, position in ordinals.items():
            if node._stored_ordinal() != position:
                users.update(self._computed.ordinal_users(node))
        issues = {user for user in users if isinstance(user, UnresolvedReference)}
        users.difference_update(issues)
        users.difference_update(excluded)
        moved_users.difference_update(excluded)
        selections = {}
        for uid in users:
            reference = self._bindings[uid].reference
            indexed = iter(self._index_collections(reference))
            selections[uid] = {index for index, item in enumerate(reference.indices)
                               if isinstance(item, Index) and next(indexed) in changed}
        with preview_structure(children_by_parent, parents or {}, ordinals):
            for issue in issues.difference(excluded_issues):
                self._validate_reference_guards(issue, {})
            self.document._validate_structural_references(tuple(self._bindings[uid].reference for uid in users))
            for uid in moved_users:
                binding = self._bindings[uid]
                positions, _ = self._positions(binding.reference, {}, check_keys=False)
                selections[uid].update(index for index, item in enumerate(binding.reference.indices)
                                       if isinstance(item, Index) and positions[index] != binding.positions[index])
            plan = self._plan_value_overrides({}, index_selection=selections, seeds=users,
                                             excluded=excluded, excluded_issues=excluded_issues)
            self._validate_managed_values(plan)
            return plan

    def refresh_structure(self, nodes):
        users = {uid for node in nodes for uid in self._content_users.get(node, ())}
        for uid in users:
            reference = self._bindings[uid].reference
            self._unindex_values(reference)
            self._untrack_collections(reference)
            self._index_values(reference)
            self._track_collections(reference)

    def _validate_managed_values(self, plan):
        for binding, positions, _ in plan:
            for item, previous, position in zip(binding.reference.indices, binding.values, positions):
                current = item.field.arguments[item.argument]
                if current is not previous and current.value not in (previous.value, position):
                    raise ReferenceError(f'{binding.reference.role}: managed index edited; retarget the reference instead')

    def _positions(self, reference, orders, *, overrides=None, check_keys=True):
        def read(owner, argument):
            if overrides:
                slot = self._source_slot(owner, argument)
                if slot in overrides:
                    return overrides[slot]
            if isinstance(argument, _NamedArgument):
                value = owner[argument.name]
                if isinstance(value, tuple):
                    value = value[argument.argument]
                elif argument.argument != 0:
                    raise IndexError(argument.argument)
                return Value.of(value)
            return owner.arguments[argument]

        def key_source(target, name):
            owner, argument = self._property_source(target, name, 0)
            definition = target.schema.fields.get(name) if target.schema is not None else None
            calculated = definition is not None and definition.getter is not None
            if owner is None or (calculated and definition.kind == 'tuple') or (
                    not calculated and len(owner.arguments) != 1):
                return None, None
            return owner, argument

        anchor = reference.target
        if isinstance(anchor, Segment):
            start, end = anchor.start, anchor.end
            parent = start.parent
            if parent is None or end.parent is not parent or start.kind != end.kind:
                raise ReferenceError(f'{reference.role}: segment endpoints have separated')
            first, last = start._ordinal(), end._ordinal()
            if abs(first-last) != 1:
                raise ReferenceError(f'{reference.role}: segment was split; choose the new attachment segment')
            anchor = start if first > last else end
        result, domains = [], []
        for item in reference.indices:
            target = anchor
            if item.ancestor < 0:
                raise ReferenceError('ancestor depth must be nonnegative')
            for _ in range(item.ancestor):
                target = target.parent
                if target is None:
                    raise ReferenceError(f'{reference.role}: target has no required ancestor')
            parent = target.parent
            if parent is None:
                raise ReferenceError(f'{reference.role}: target is outside an indexed collection')
            if isinstance(item, Property):
                owner, argument = self._property_source(target, item.name, item.target_argument)
                if owner is None or item.target_argument < 0:
                    raise ReferenceError(f'{reference.role}: target property is missing')
                try:
                    value = read(owner, argument)
                except IndexError:
                    raise ReferenceError(f'{reference.role}: target property is missing') from None
                except TypeError:
                    raise ReferenceError(f'{reference.role}: target property must be a scalar') from None
                current = item.field.arguments[item.argument]
                if value.kind not in ('number', 'string', 'symbol', 'boolean') or (current.kind, current.unit) != (value.kind, value.unit):
                    raise ReferenceError(f'{reference.role}: property types/units disagree')
                result.append(value.value)
                domains.append(('property', target.kind, parent.kind, item.name, item.target_argument, value.kind, value.unit))
                continue
            if isinstance(item, Key):
                owner, argument = key_source(target, item.name)
                if owner is None:
                    raise ReferenceError(f'{reference.role}: target needs one {item.name} key')
                value = read(owner, argument)
                if value.kind not in ('number', 'string', 'symbol') or value.unit:
                    raise ReferenceError(f'{reference.role}: invalid {item.name} key')
                if check_keys:
                    cache_key = ('keys', parent, target.kind, item.name)
                    if cache_key not in orders:
                        keys = {}
                        for child in parent.children(target.kind):
                            owner, argument = key_source(child, item.name)
                            if owner is not None:
                                key_value = read(owner, argument).value
                                keys[key_value] = child if key_value not in keys else None
                        orders[cache_key] = keys
                    if orders[cache_key].get(value.value) is not target:
                        raise ReferenceError(f'{reference.role}: duplicate {item.name} key')
                result.append(value.value)
                domains.append(('key', target.kind, parent.kind, item.name))
                continue
            result.append(target._ordinal() + item.offset)
            domains.append((target.kind, parent.kind))
        return tuple(result), tuple(domains)

    def _check(self, reference):
        root = self.document.root
        targets = (reference.target.start, reference.target.end) if isinstance(reference.target, Segment) else (reference.target,)
        if not _within(reference.source, root) or any(not _within(target, root) for target in targets):
            raise ReferenceError(f'{reference.role}: source or target is detached from this document')
        for item in reference.indices:
            if not _within(item.field, reference.source):
                raise ReferenceError(f'{reference.role}: index field has left its source element')
            try:
                value = item.field.arguments[item.argument]
            except IndexError:
                raise ReferenceError(f'{reference.role}: index argument is missing') from None
            if isinstance(item, Property):
                if item.argument < 0:
                    raise ReferenceError('property argument must be nonnegative')
            elif isinstance(item, Key):
                if item.argument < 0 or value.kind not in ('number', 'string', 'symbol') or value.unit:
                    raise ReferenceError(f'{reference.role}: a key reference needs an unqualified scalar')
            elif item.argument < 0 or value.kind != 'number' or value.unit or int(value.value) != value.value:
                raise ReferenceError(f'{reference.role}: an index must be an unqualified integer')
        self._validate_reference_guards(reference, {})

    def _prepare_binding(self, source, target, indices, *, role, guards, preserve, structure=None):
        if self._binding_orders is not None and not preserve:
            raise ReferenceError('binding batches require preserve=True')
        reference = Reference(uuid4().hex, source, target, role, tuple(indices), tuple(guards))
        slots = [item.field._argument_owner(item.argument) for item in indices]
        if len(set(slots)) != len(slots) or any(slot in self._slots for slot in slots):
            raise ReferenceError('an index slot already has a reference')
        self._check(reference)
        self.document._validate_reference_change(reference, target)
        orders = self._binding_orders if self._binding_orders is not None else {}
        positions, domains = self._positions(reference, orders, check_keys=preserve)
        self._validate_copy_cycles(reference)
        values = tuple(i.field.arguments[i.argument] for i in indices)
        binding = _Binding(reference, values, positions, domains, self._next_sequence)
        plan = ()
        if self.document._automatic_structure:
            plan = self._plan_reference_changes({reference.uid: reference}, extra=None if preserve else binding,
                                                 structure=structure)
        elif not preserve:
            plan = self._plan_value_overrides({}, extra=binding)
        return binding, slots, plan

    def _register_binding(self, binding, slots, plan, *, preserve):
        reference = binding.reference
        source = reference.source
        if not preserve:
            self._pending_index_collections.update(self._index_collections(reference))
        self._bindings[reference.uid] = binding
        self._next_sequence += 1
        self._outgoing.setdefault(source, {})[reference.uid] = None
        for target in self._targets(reference):
            self._incoming.setdefault(target, {})[reference.uid] = None
        self._index_values(reference)
        self._index_guards(reference)
        self._track_collections(reference)
        self._slots.update((slot, reference.uid) for slot in slots)
        for slot in slots:
            self._unresolved_values.pop(slot, None)
        for issue in tuple(self.issues):
            if issue.indices and all(self.manages(i.field, i.argument) for i in issue.indices):
                self.discard_issue(issue)
        self.apply_value_change(plan)
        return reference

    def bind(self, source, target, *indices, role='', guards=(), preserve=False):
        prepared = self._prepare_binding(source, target, indices, role=role, guards=guards, preserve=preserve)
        return self._register_binding(*prepared, preserve=preserve)

    def _prepare_additions(self, specifications, *, structure=None):
        """Preflight a related group of new links against one prospective graph."""
        references, reserved = [], set()
        for source, target, role, indices, guards in specifications:
            if any(item is None for item in indices):
                continue
            slots = {item.field._argument_owner(item.argument) for item in indices}
            if slots and all(slot in self._slots for slot in slots):
                if any(self._bindings[self._slots[slot]].reference.role != role for slot in slots):
                    raise ReferenceError('reference field already belongs to a different relationship')
                continue
            if any(slot in self._unresolved_values for slot in slots):
                continue
            if len(slots) != len(indices) or slots.intersection(self._slots) or slots.intersection(reserved):
                raise ReferenceError('an index slot already has a reference')
            if not slots and any(reference.role == role for reference in self.outgoing(source)):
                raise ReferenceError('source already has this identity relationship')
            reserved.update(slots)
            references.append(Reference(uuid4().hex, source, target, role, tuple(indices), tuple(guards)))
        changes = {reference.uid: reference for reference in references}
        bindings = []
        with preview_references(self, changes):
            for reference in references:
                self._check(reference)
                self.document._validate_reference_change(reference, reference.target)
                positions, domains = self._positions(reference, {}, check_keys=False)
                values = tuple(item.field.arguments[item.argument] for item in reference.indices)
                bindings.append(_Binding(reference, values, positions, domains, self._next_sequence+len(bindings)))
            if references:
                self._validate_copy_cycles(references[0], companions=references[1:])
            plan = self._plan_reference_changes(changes, extra=bindings, structure=structure)
        return _Additions(tuple(bindings), plan)

    def _record_references(self, record):
        users = set(self._content_users.get(record, ()))
        if record.parent is not None:
            users.update(self._collection_users.get((record.parent, record.kind), ()))
        return tuple(self._bindings[uid].reference for uid in users)

    def _content_references(self, nodes):
        users = {uid for node in nodes for uid in self._content_users.get(node, ())}
        return tuple(sorted((self._bindings[uid].reference for uid in users), key=self._sequence))

    def _content_issues(self, nodes):
        issues = {issue for node in nodes for issue in self._issues_by_node.get(node, ())}
        return tuple(sorted(issues, key=self._issue_sequence.__getitem__))

    def _apply_additions(self, additions):
        """Register a preflighted topology before evaluating calculated inputs."""
        for binding in additions.bindings:
            reference = binding.reference
            self._bindings[reference.uid] = binding
            self._outgoing.setdefault(reference.source, {})[reference.uid] = None
            for target in self._targets(reference):
                self._incoming.setdefault(target, {})[reference.uid] = None
        self._next_sequence += len(additions.bindings)
        for binding in additions.bindings:
            reference = binding.reference
            self._index_values(reference)
            self._index_guards(reference)
            self._track_collections(reference)
            self._slots.update((item.field._argument_owner(item.argument), reference.uid) for item in reference.indices)
            self._pending_index_collections.update(self._index_collections(reference))
        self.apply_value_change(additions.projections)

    def _attach_bound(self, parent, node, target, *indices, role='', guards=()):
        """Attach one new source and its link after a combined prospective check."""
        if node.parent is not None or node._document is not None or not node.kind:
            raise ValueError('a new linked record must be detached')
        if parent._owner() is not self.document:
            raise ReferenceError('attachment parent is outside this document')
        children = (*parent._child_sequence(), node)
        validate_child_change(parent, children, node.kind)
        structure = self.plan_collections({parent: children}, parents={node: parent})
        counts, ordinals = {}, {}
        for child in children:
            ordinals[child] = counts.get(child.kind, 0)
            counts[child.kind] = ordinals[child] + 1
        with preview_structure({parent: children}, {node: parent}, ordinals):
            prepared = self._prepare_binding(node, target, indices, role=role, guards=guards,
                                               preserve=False, structure=structure)
        parent._items.append(node)
        node._parent = parent
        parent._touch(reordered=True)
        reference = self._register_binding(*prepared, preserve=False)
        self.finish_structure((parent,))
        return reference

    def _index_collections(self, reference):
        anchor = reference.target.start if isinstance(reference.target, Segment) else reference.target
        for item in reference.indices:
            if isinstance(item, Index):
                target = anchor
                for _ in range(item.ancestor):
                    target = target.parent
                yield target.parent, target.kind

    def _write(self, binding, positions, *, selected=None):
        for ordinal, (item, position, domain) in enumerate(zip(binding.reference.indices, positions, binding.domains)):
            if selected is not None and ordinal not in selected:
                continue
            old = item.field.arguments[item.argument]
            item.field.set_argument(item.argument, self._projected_value(item, position, domain, source=old.source))
        binding.values = tuple(i.field.arguments[i.argument] for i in binding.reference.indices)
        binding.positions = positions

    def retarget(self, reference, target):
        binding = self._bindings[reference.uid]
        replacement = replace(binding.reference, target=target)
        self._check(replacement)
        positions, domains = self._positions(replacement, {}, check_keys=False)
        if domains != binding.domains:
            raise ReferenceError('new target belongs to an incompatible collection')
        self.document._validate_reference_change(binding.reference, target)
        self._validate_copy_cycles(replacement)
        prospective = _Binding(replacement, binding.values, positions, domains, binding.sequence)
        plan = (self._plan_reference_changes({reference.uid: replacement}, extra=prospective)
                if self.document._automatic_structure else self._plan_value_overrides({}, extra=prospective))
        for old_target in self._targets(binding.reference):
            self._unindex(self._incoming, old_target, reference.uid)
        self._unindex_values(binding.reference)
        self._untrack_collections(binding.reference)
        binding.reference = replacement
        for new_target in self._targets(replacement):
            self._incoming.setdefault(new_target, {})[reference.uid] = None
        self._index_values(replacement)
        self._track_collections(replacement)
        plan = _ProjectionPlan(tuple((binding if entry is prospective else entry, positions, selected)
                                     for entry, positions, selected in plan), plan.values, plan.calculations)
        self.apply_value_change(plan)
        self._pending_index_collections.update(self._index_collections(replacement))
        return replacement

    def discard(self, reference):
        """Remove a binding; leave the source fields available for explicit edits."""
        plan = ()
        if self.document._automatic_structure:
            self.document._validate_reference_removal(self._bindings[reference.uid].reference)
            plan = self._plan_reference_changes({reference.uid: None})
        self._discard_bindings((reference,))
        self.apply_value_change(plan)

    def _discard_bindings(self, references):
        """Commit removals already checked as a collective operation."""
        for reference in references:
            binding = self._bindings.pop(reference.uid)
            self._unindex(self._outgoing, binding.reference.source, reference.uid)
            for target in self._targets(binding.reference):
                self._unindex(self._incoming, target, reference.uid)
            self._unindex_values(binding.reference)
            self._unindex_guards(binding.reference)
            self._untrack_collections(binding.reference)
            for item in binding.reference.indices:
                del self._slots[item.field._argument_owner(item.argument)]

    def _renumbering_collision(self, issue, collections, orders):
        """Would a projected target acquire the unresolved link's whole key?"""
        affected = collections if issue.collections is None else collections.intersection(issue.collections)
        values = tuple(item.field.values[item.argument] for item in issue.indices)
        for parent in affected:
            for target in parent.walk():
                candidate = Reference('', issue.source, target, 'unresolved target', issue.indices)
                try:
                    positions, _ = self._positions(candidate, orders)
                    if not any(owner in affected for owner, kind in self._index_collections(candidate)):
                        continue
                except ReferenceError:
                    continue  # This record cannot supply the required ancestor/property domain.
                if positions == values:
                    return True
        return False

    def _synchronization_plan(self, *, force=False):
        # Validate every operation before changing any serialized index.
        if self.issues:
            for issue in self.issues:
                self._validate_reference_guards(issue, {})
                if (not _within(issue.source, self.document.root) or
                        any(not _within(item.field, issue.source) for item in issue.indices)):
                    raise ReferenceError('unresolved reference content is detached from this document')
                parents = self._watched if issue.collections is None else issue.collections
                if any(not _within(parent, self.document.root) or tuple(parent.children()) != self._watched[parent]
                       for parent in parents):
                    raise ReferenceError('unresolved references prevent rebuilding changed collections')
            for (field, argument), value in self._unresolved_values.items():
                current = field.arguments[argument]
                if (current.kind, current.value, current.unit) != (value.kind, value.value, value.unit):
                    raise ReferenceError('an unresolved reference was edited; bind its target explicitly')
        orders, plan = {}, []
        changed_collections = set(self._pending_index_collections)
        for binding in self._bindings.values():
            reference = binding.reference
            self._check(reference)
            positions, domains = self._positions(reference, orders, check_keys=False)
            if domains != binding.domains:
                raise ReferenceError(f'{reference.role}: target moved into an incompatible collection')
            plan.append((binding, positions))
            index_changed = any(isinstance(item, Index) and (position != old or current.value != previous.value)
                                for item, position, old, current, previous in
                                zip(reference.indices, positions, binding.positions,
                                    (item.field.arguments[item.argument] for item in reference.indices), binding.values))
            if index_changed:
                # Saved numeric IDs can have gaps. If one member moves, all
                # positional projections into that collection must use the
                # current numbering, including members whose position stayed
                # the same. Otherwise an untouched saved key can collide with
                # a moved member's newly projected ordinal.
                changed_collections.update(self._index_collections(reference))
        # Unresolved slots still use the collection's current numbering. Even
        # with unchanged record order, canonicalizing saved keys with gaps can
        # give a missing key an unrelated target. Compare the whole projected
        # key: a missing route or invalid segment need not freeze safe rekeying.
        # Validate the entire plan before writing values.
        if self.issues:
            renumbered = set()
            for binding, positions in plan:
                indexed = iter(self._index_collections(binding.reference))
                for item, position in zip(binding.reference.indices, positions):
                    if isinstance(item, Index):
                        collection = next(indexed)
                        if (force or collection in changed_collections) and item.field.values[item.argument] != position:
                            renumbered.add(collection[0])
            if any(self._renumbering_collision(issue, renumbered, orders) for issue in self.issues):
                raise ReferenceError('unresolved references prevent renumbering these collections')
        overrides, selections = {}, {}
        for binding, positions in plan:
            selected = set()
            collections = iter(self._index_collections(binding.reference))
            for index, (item, position, previous, domain) in enumerate(
                    zip(binding.reference.indices, positions, binding.positions, binding.domains)):
                if isinstance(item, Index):
                    collection = next(collections)
                    if force or position != previous or collection in changed_collections:
                        selected.add(index)
                        overrides[item.field._argument_owner(item.argument)] = self._projected_value(item, position, domain)
            selections[binding.reference.uid] = selected
        projected = self._plan_value_overrides(overrides, index_selection=selections, force=force, all_bindings=True)
        self._validate_managed_values(projected)
        return projected

    def validate(self):
        """Audit links and pending projections without writing any field."""
        self._synchronization_plan()

    def synchronize(self, *, force=False):
        self.apply_value_change(self._synchronization_plan(force=force))
        self._pending_index_collections.clear()

    def clone_to(self, document, mapping):
        graph = References(document)
        document.references = graph
        graph._pending_index_collections = {(mapping[parent], kind) for parent, kind in self._pending_index_collections
                                            if parent in mapping}

        def mapped(node):
            try:
                return mapping[node]
            except KeyError:
                raise ReferenceError('cannot clone a document with detached reference content') from None

        def copied_guard(guard):
            changes = {'field': mapped(guard.field)}
            if isinstance(guard, OrdinalGuard):
                changes['member'] = mapped(guard.member)
            return replace(guard, **changes)

        # Register the complete topology before evaluating any calculated field.
        # A property's producer may appear later in the graph's semantic order.
        for binding in self._bindings.values():
            r = binding.reference
            indices = tuple(replace(i, field=mapped(i.field)) for i in r.indices)
            guards = tuple(copied_guard(g) for g in r.guards)
            target = (Segment(mapped(r.target.start), mapped(r.target.end)) if isinstance(r.target, Segment)
                      else mapped(r.target))
            copied = Reference(uuid4().hex, mapped(r.source), target, r.role, indices, guards)
            graph._bindings[copied.uid] = _Binding(copied, binding.values, binding.positions,
                                                  binding.domains, binding.sequence)
            graph._outgoing.setdefault(copied.source, {})[copied.uid] = None
            for anchor in graph._targets(copied):
                graph._incoming.setdefault(anchor, {})[copied.uid] = None
        graph._next_sequence = self._next_sequence
        for copied in graph:
            graph._check(copied)
            graph._positions(copied, {})
            graph._index_values(copied)
            graph._index_guards(copied)
            graph._track_collections(copied)
            graph._slots.update((item.field._argument_owner(item.argument), copied.uid) for item in copied.indices)
        for issue in self.issues:
            indices = tuple(replace(i, field=mapped(i.field)) for i in issue.indices)
            collections = None if issue.collections is None else tuple(mapped(parent) for parent in issue.collections)
            guards = tuple(copied_guard(guard) for guard in issue.guards)
            graph.note(mapped(issue.source), issue.message, *indices, collections=collections, guards=guards)
        if self.issues:
            required = (set(self._watched) if any(issue.collections is None for issue in self.issues)
                        else {parent for issue in self.issues for parent in issue.collections})
            graph._watched = {mapped(parent): tuple(mapped(node) for node in children if parent in required or node in mapping)
                              for parent, children in self._watched.items() if parent in required or parent in mapping}
        else:
            graph._watched = {mapping[parent]: tuple(mapping[node] for node in children if node in mapping)
                              for parent, children in self._watched.items() if parent in mapping}
        return graph
