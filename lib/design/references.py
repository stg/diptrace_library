"""Identity-based links, with positional indices projected only when rebuilding.

A target can supply several serialized indices. For example, one pin supplies
its own index and the index of its containing component. The graph itself knows
nothing about a particular file format or electrical model.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from contextlib import contextmanager
from uuid import uuid4

from .model import Element, Value


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
    guards: tuple[Guard, ...] = ()


@dataclass(frozen=True)
class UnresolvedReference:
    source: Element
    message: str
    indices: tuple[Index | Key | Property, ...]
    collections: tuple[Element, ...] | None = None


@dataclass
class _Binding:
    reference: Reference
    values: tuple[Value, ...]
    positions: tuple[object, ...]
    domains: tuple[tuple[str, ...], ...]


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
        self._slots: dict[tuple[Element, int], str] = {}
        self.issues: list[UnresolvedReference] = []
        self._unresolved_values = {}
        self._watched = {}
        self._binding_orders = None
        self._pending_index_collections = set()

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
        return len(self._bindings)

    def __iter__(self):
        return (binding.reference for binding in self._bindings.values())

    def get(self, uid):
        try:
            return self._bindings[uid].reference
        except KeyError:
            raise LookupError(f'unknown reference identity: {uid}') from None

    def incoming(self, target, *, role=None):
        return [r for r in self if (r.target is target or isinstance(r.target, Segment) and
                                   target in (r.target.start, r.target.end)) and
                (role is None or r.role == role)]

    def outgoing(self, source, *, role=None):
        return [r for r in self if r.source is source and (role is None or r.role == role)]

    def manages(self, field, argument=0):
        return (field, argument) in self._slots

    def unresolved_slot(self, field, argument=0):
        return (field, argument) in self._unresolved_values

    def note(self, source, message, *indices, collections=None):
        if collections is not None:
            collections = tuple(dict.fromkeys(collections))
            if any(not isinstance(parent, Element) or not _within(parent, self.document.root) for parent in collections):
                raise ReferenceError('unresolved reference scope is outside this document')
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
        issue = UnresolvedReference(source, message, tuple(indices), collections)
        self.issues.append(issue)
        for item in indices:
            self._unresolved_values[item.field, item.argument] = item.field.arguments[item.argument]
        return issue

    def discard_issue(self, issue):
        """Explicitly stop tracking an unresolved link, for deletion/replacement."""
        if issue not in self.issues:
            raise LookupError('unresolved reference is not registered here')
        self.issues.remove(issue)
        remaining = {(item.field, item.argument) for other in self.issues for item in other.indices}
        for item in issue.indices:
            slot = item.field, item.argument
            if slot not in remaining:
                self._unresolved_values.pop(slot, None)

    def watch(self, collection):
        self._watched.setdefault(collection, tuple(collection.children()))

    def _check_collection_changes(self, collections):
        """Preflight a structural edit before detaching any records."""
        changed = set(collections)
        if changed and any(issue.collections is None or changed.intersection(issue.collections)
                           for issue in self.issues):
            raise ReferenceError('unresolved references prevent changing these collections')

    def _positions(self, reference, orders):
        anchor = reference.target
        if isinstance(anchor, Segment):
            start, end = anchor.start, anchor.end
            parent = start.parent
            if parent is None or end.parent is not parent or start.kind != end.kind:
                raise ReferenceError(f'{reference.role}: segment endpoints have separated')
            key = parent, start.kind
            if key not in orders:
                orders[key] = {child: i for i, child in enumerate(parent.children(start.kind))}
            first, last = orders[key][start], orders[key][end]
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
                fields = target.children(item.name) if item.name is not None else [target]
                owner = fields[0] if len(fields) == 1 else None
                if owner is None or item.target_argument < 0 or item.target_argument >= len(owner.arguments):
                    raise ReferenceError(f'{reference.role}: target property is missing')
                if self.manages(owner, item.target_argument) or owner is item.field and item.target_argument == item.argument:
                    raise ReferenceError(f'{reference.role}: property target is managed; bind directly to its target instead')
                value = owner.arguments[item.target_argument]
                current = item.field.arguments[item.argument]
                if value.kind not in ('number', 'string', 'symbol', 'boolean') or (current.kind, current.unit) != (value.kind, value.unit):
                    raise ReferenceError(f'{reference.role}: property types/units disagree')
                result.append(value.value)
                domains.append(('property', target.kind, parent.kind, item.name, item.target_argument, value.kind, value.unit))
                continue
            if isinstance(item, Key):
                fields = target.children(item.name)
                if len(fields) != 1 or len(fields[0].arguments) != 1:
                    raise ReferenceError(f'{reference.role}: target needs one {item.name} key')
                value = fields[0].arguments[0]
                if value.kind not in ('number', 'string', 'symbol') or value.unit:
                    raise ReferenceError(f'{reference.role}: invalid {item.name} key')
                cache_key = ('keys', parent, target.kind, item.name)
                if cache_key not in orders:
                    keys = {}
                    for child in parent.children(target.kind):
                        fields = child.children(item.name)
                        if len(fields) == 1 and len(fields[0].arguments) == 1:
                            key_value = fields[0].values[0]
                            keys[key_value] = child if key_value not in keys else None
                    orders[cache_key] = keys
                if orders[cache_key].get(value.value) is not target:
                    raise ReferenceError(f'{reference.role}: duplicate {item.name} key')
                result.append(value.value)
                domains.append(('key', target.kind, parent.kind, item.name))
                continue
            key = parent, target.kind
            if key not in orders:
                orders[key] = {child: i for i, child in enumerate(parent.children(target.kind))}
            result.append(orders[key][target] + item.offset)
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
        for guard in reference.guards:
            if not _within(guard.field, reference.source) or guard.field.values != guard.values:
                raise ReferenceError(f'{reference.role}: reference mode changed; bind its new target explicitly')

    def bind(self, source, target, *indices, role='', guards=(), preserve=False):
        if self._binding_orders is not None and not preserve:
            raise ReferenceError('binding batches require preserve=True')
        reference = Reference(uuid4().hex, source, target, role, tuple(indices), tuple(guards))
        if not indices:
            raise ReferenceError('a reference needs at least one index projection')
        slots = [(item.field, item.argument) for item in indices]
        if len(set(slots)) != len(slots) or any(slot in self._slots for slot in slots):
            raise ReferenceError('an index slot already has a reference')
        self._check(reference)
        orders = self._binding_orders if self._binding_orders is not None else {}
        positions, domains = self._positions(reference, orders)
        values = tuple(i.field.arguments[i.argument] for i in indices)
        binding = _Binding(reference, values, positions, domains)
        if not preserve:
            self._write(binding, positions)
            self._pending_index_collections.update(self._index_collections(reference))
        self._bindings[reference.uid] = binding
        self._slots.update((slot, reference.uid) for slot in slots)
        for slot in slots:
            self._unresolved_values.pop(slot, None)
        self.issues = [issue for issue in self.issues
                       if not all(self.manages(i.field, i.argument) for i in issue.indices)]
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
            kind, unit = (domain[-2], domain[-1]) if isinstance(item, Property) else (
                'string' if isinstance(position, str) else 'number', '')
            item.field.set_argument(item.argument, Value(position, kind, unit, source=old.source))
        binding.values = tuple(i.field.arguments[i.argument] for i in binding.reference.indices)
        binding.positions = positions

    def retarget(self, reference, target):
        binding = self._bindings[reference.uid]
        replacement = replace(binding.reference, target=target)
        self._check(replacement)
        positions, domains = self._positions(replacement, {})
        if domains != binding.domains:
            raise ReferenceError('new target belongs to an incompatible collection')
        binding.reference = replacement
        self._write(binding, positions)
        self._pending_index_collections.update(self._index_collections(replacement))
        return replacement

    def discard(self, reference):
        """Remove a binding; leave the source fields available for explicit edits."""
        binding = self._bindings.pop(reference.uid)
        for item in binding.reference.indices:
            del self._slots[item.field, item.argument]

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

    def synchronize(self, *, force=False):
        # Validate every operation before changing any serialized index.
        if self.issues:
            for issue in self.issues:
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
            positions, domains = self._positions(reference, orders)
            if domains != binding.domains:
                raise ReferenceError(f'{reference.role}: target moved into an incompatible collection')
            for item, previous, position in zip(reference.indices, binding.values, positions):
                current = item.field.arguments[item.argument]
                if current is not previous and current.value not in (previous.value,position):
                    raise ReferenceError(f'{reference.role}: managed index edited; retarget the reference instead')
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
        for binding, positions in plan:
            if force:
                self._write(binding, positions)
            else:
                selected = {index for index, (position, previous) in enumerate(zip(positions, binding.positions))
                            if position != previous}
                if changed_collections:
                    indexed = iter(self._index_collections(binding.reference))
                    for index, item in enumerate(binding.reference.indices):
                        if isinstance(item, Index) and next(indexed) in changed_collections:
                            selected.add(index)
                self._write(binding, positions, selected=selected)
        self._pending_index_collections.clear()

    def clone_to(self, document, mapping):
        graph = References(document)
        graph._pending_index_collections = {(mapping[parent], kind) for parent, kind in self._pending_index_collections
                                            if parent in mapping}

        def mapped(node):
            try:
                return mapping[node]
            except KeyError:
                raise ReferenceError('cannot clone a document with detached reference content') from None

        with graph.binding_batch():
            for binding in self._bindings.values():
                r = binding.reference
                indices = tuple(replace(i, field=mapped(i.field)) for i in r.indices)
                guards = tuple(replace(g, field=mapped(g.field)) for g in r.guards)
                target = (Segment(mapped(r.target.start), mapped(r.target.end)) if isinstance(r.target, Segment)
                          else mapped(r.target))
                copied = graph.bind(mapped(r.source), target, *indices,
                                    role=r.role, guards=guards, preserve=True)
                # Retain pending projections when cloning an edited document.
                graph._bindings[copied.uid].positions = binding.positions
                graph._bindings[copied.uid].domains = binding.domains
                graph._bindings[copied.uid].values = binding.values
        for issue in self.issues:
            indices = tuple(replace(i, field=mapped(i.field)) for i in issue.indices)
            collections = None if issue.collections is None else tuple(mapped(parent) for parent in issue.collections)
            graph.note(mapped(issue.source), issue.message, *indices, collections=collections)
        if self.issues:
            required = (set(self._watched) if any(issue.collections is None for issue in self.issues)
                        else {parent for issue in self.issues for parent in issue.collections})
            graph._watched = {mapped(parent): tuple(mapped(node) for node in children if parent in required or node in mapping)
                              for parent, children in self._watched.items() if parent in required or parent in mapping}
        else:
            graph._watched = {mapping[parent]: tuple(mapping[node] for node in children if node in mapping)
                              for parent, children in self._watched.items() if parent in mapping}
        return graph
