"""Compact record content and lazy field views behind the Element facade.

The value vector is authoritative. Ordered positions identify fields without
allocating a leaf Element for each one. Explicitly requested leaves use the
same editing/ownership machinery as ordinary elements.
"""
from collections.abc import MutableSequence
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from weakref import WeakValueDictionary

from .record_storage import RecordStorage, _FieldPosition
from .schema import MISSING


_NO_RECORDS = MappingProxyType({None: ()})
_EMPTY_MAP = MappingProxyType({})


def _bind_model_types(element, value):
    """Complete the model/storage cycle once, instead of importing per field."""
    global Element, Value
    Element, Value = element, value


def _kind(value):
    return 'null' if value is None else 'boolean' if isinstance(value, bool) else 'string' if isinstance(value, str) else 'number'


@dataclass(slots=True)
class _Details:
    source: object = None
    notes: object = None
    arguments: tuple = ()


@dataclass(slots=True)
class _Malformed:
    items: list


class FieldItems(MutableSequence):
    """Argument view over a field slot; retained leaves never own a value copy."""
    __slots__ = ('record', 'slot')

    def __init__(self, record, slot):
        self.record, self.slot = record, slot

    @property
    def definition(self):
        return self.record.storage.layout.definitions[self.slot]

    def values(self):
        value = self.record.storage._values[self.slot]
        if isinstance(value, _Malformed):
            return tuple(item.value for item in value.items if isinstance(item, Value))
        return value if self.definition.kind == 'tuple' else (value,)

    def __len__(self):
        value = self.record.storage._values[self.slot]
        return len(value.items) if isinstance(value, _Malformed) else len(value) if self.definition.kind == 'tuple' else 1

    def __getitem__(self, index):
        value = self.record.storage._values[self.slot]
        if isinstance(value, _Malformed):
            return value.items[index]
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self))) ]
        return self.record.argument(self.slot, index)

    def __setitem__(self, index, value):
        items = list(self)
        items[index] = value
        self.replace(items)

    def __delitem__(self, index):
        items = list(self)
        del items[index]
        self.replace(items)

    def insert(self, index, value):
        items = list(self)
        items.insert(index, value)
        self.replace(items)

    def replace(self, items):
        self.record.store_arguments(self.slot, list(items))

    def detach(self, node):
        node._dirty_flag, node._reordered_flag = node._dirty, node._reordered
        node._content = list(self)
        detail = self.record.details.get(self.slot)
        node._source = detail.source if detail is not None else None

    def source(self):
        detail = self.record.details.get(self.slot)
        return detail.source if detail is not None else None

    def set_source(self, source):
        if source is not None or self.slot in self.record.details:
            self.record.detail(self.slot).source = source

    def set_notes(self, notes):
        self.record.detail(self.slot).notes = notes

    def remember_uid(self, uid):
        self.record.remember_uid(self.slot, uid)

    def children(self, kind=None):
        value = self.record.storage._values[self.slot]
        return tuple(item for item in value.items if isinstance(item, Element) and
                     (kind is None or item.kind == kind)) if isinstance(value, _Malformed) else ()

class RecordItems(MutableSequence):
    """Mixed owned records/arguments and shared field positions.

    Weak handle caching preserves live object identity without retaining every
    field merely because an inspection walked it once. Observed UIDs survive
    handle collection in a separate private address map.
    """
    __slots__ = ('owner', 'storage', 'order', 'handles', 'identities', 'details',
                 'retain_debug', '_records', 'dirty_fields', 'reordered_fields')

    def __init__(self, owner, schema, items=(), *, retain_debug=False):
        self.owner = owner
        self.storage = RecordStorage(schema)
        self.order = []
        self.handles = self.identities = self.details = _EMPTY_MAP
        self.retain_debug = retain_debug
        self._records = None
        self.dirty_fields = self.reordered_fields = 0
        for item in items:
            self.insert(len(self.order), item)

    def __len__(self):
        return len(self.order)

    def __iter__(self):
        for item in self.order:
            yield self.field(item.index) if isinstance(item, _FieldPosition) else item

    def __getitem__(self, index):
        item = self.order[index]
        if isinstance(index, slice):
            return [self.field(row.index) if isinstance(row, _FieldPosition) else row for row in item]
        return self.field(item.index) if isinstance(item, _FieldPosition) else item

    def __setitem__(self, index, value):
        items = list(self)
        items[index] = value
        self.replace(items)

    def index(self, value, start=0, stop=None):
        content = getattr(value, '_content', None)
        if type(content) is FieldItems and content.record is self:
            value = self.storage.layout.positions[content.slot]
        return self.order.index(value, start, len(self.order) if stop is None else stop)

    def __delitem__(self, index):
        if isinstance(index, slice):
            items = list(self)
            del items[index]
            self.replace(items)
            return
        item = self.order[index]
        owned_changed = not isinstance(item, _FieldPosition) or isinstance(self.storage._values[item.index], _Malformed)
        if isinstance(item, _FieldPosition):
            self._remove_field(item.index)
        del self.order[index]
        self._sync_order()
        if owned_changed:
            self._records = None

    def detail(self, slot):
        value = self.details.get(slot)
        if value is None:
            if self.details is _EMPTY_MAP:
                self.details = {}
            value = self.details[slot] = _Details()
        return value

    def remember_uid(self, slot, uid):
        if self.identities is _EMPTY_MAP:
            self.identities = {}
        self.identities[slot] = uid

    def _cache_handle(self, slot, node):
        if self.handles is _EMPTY_MAP:
            self.handles = WeakValueDictionary()
        self.handles[slot] = node

    def field(self, slot):
        node = self.handles.get(slot)
        if node is None:
            node = Element(self.storage.layout.names[slot])
            node._uid = self.identities.get(slot)
            node._parent = self.owner
            node._content = FieldItems(self, slot)
            node._source = None
            detail = self.details.get(slot)
            node._annotations = detail.notes if detail is not None else None
            node._dirty = bool(self.dirty_fields & (1 << slot))
            node._reordered = bool(self.reordered_fields & (1 << slot))
            self._cache_handle(slot, node)
        return node

    def store_arguments(self, slot, items):
        definition = self.storage.layout.definitions[slot]
        if isinstance(self.storage._values[slot], _Malformed):
            self._records = None
        if (all(isinstance(item, Value) for item in items)
                and (definition.kind == 'tuple' or len(items) == 1)):
            values = tuple(item.value for item in items)
            self.storage._store(slot, values if definition.kind == 'tuple' else values[0])
            metadata = tuple((item.kind, item.unit,
                              item.lexeme if self.retain_debug else None,
                              item.source if self.retain_debug else None)
                             if item.kind != _kind(item.value) or item.unit or
                                self.retain_debug and (item.lexeme is not None or item.source is not None)
                             else None for item in items)
            if any(item is not None for item in metadata):
                self.detail(slot).arguments = metadata
            elif slot in self.details:
                self.details[slot].arguments = ()
        else:
            self.storage._store(slot, _Malformed(items))
            self._records = None

    def _import_slot(self, name, replace):
        slot = self.storage.layout.slots.get(name)
        if not self.can_import(name, replace=replace):
            return None
        if name not in self.storage:
            self.order.append(self.storage.layout.positions[slot])
        self.dirty_fields |= 1 << slot
        self.reordered_fields |= 1 << slot
        return slot

    def can_import(self, name, *, replace=False):
        slot = self.storage.layout.slots.get(name)
        return (slot is not None and not self.storage.layout.definitions[slot].members
                and name not in self._owned_records() and (replace or name not in self.storage))

    def import_field(self, name, arguments, *, replace=False, source=None):
        """Store an adapter-decoded field before authoring/reference activation."""
        slot = self._import_slot(name, replace)
        if slot is None:
            return False
        self.store_arguments(slot, arguments)
        if self.retain_debug and source is not None:
            self.detail(slot).source = source
        return True

    def import_value(self, name, value, *, replace=False):
        """The ordinary scalar import path has no Value/provenance allocation."""
        slot = self._import_slot(name, replace)
        if slot is None:
            return False
        if isinstance(self.storage._values[slot], _Malformed):
            self._records = None
        self.storage._store(slot, (value,) if self.storage.layout.definitions[slot].kind == 'tuple' else value)
        if slot in self.details:
            self.details[slot].arguments = ()
        return True

    def _eligible(self, item):
        return (isinstance(item, Element) and item.schema is None and
                item.kind in self.storage.layout.slots and
                not self.storage.layout.definitions[self.storage.layout.slots[item.kind]].members and
                all(isinstance(value, Value) for value in item._items))

    def insert(self, index, item):
        owned_changed = True
        if self._eligible(item) and item.kind not in self.storage:
            slot = self.storage.layout.slots[item.kind]
            arguments = list(item._items)
            source = item.source if self.retain_debug else None
            self.store_arguments(slot, arguments)
            if source is not None or item._annotations:
                detail = self.detail(slot)
                detail.source, detail.notes = source, item._annotations
            if item._uid is not None:
                self.remember_uid(slot, item._uid)
            if item._dirty:
                self.dirty_fields |= 1 << slot
            if item._reordered:
                self.reordered_fields |= 1 << slot
            item._content = FieldItems(self, slot)
            item._source = None
            self._cache_handle(slot, item)
            self.order.insert(index, self.storage.layout.positions[slot])
            owned_changed = isinstance(self.storage._values[slot], _Malformed)
        else:
            self.order.insert(index, item)
        if index != len(self.order)-1:
            self._sync_order()
        if owned_changed:
            self._records = None

    def _remove_field(self, slot):
        handle = self.handles.pop(slot, None) if self.handles else None
        if handle is not None:
            handle._content.detach(handle)
        self.storage._values[slot] = MISSING
        self.storage._order.remove(slot)
        if self.identities:
            self.identities.pop(slot, None)
        if self.details:
            self.details.pop(slot, None)
        self.dirty_fields &= ~(1 << slot)
        self.reordered_fields &= ~(1 << slot)

    def _sync_order(self):
        self.storage._order = [item.index for item in self.order if isinstance(item, _FieldPosition)]

    def replace(self, items):
        # Retain the actual old handles until all proposed arguments are read.
        old = list(self)
        prepared = [(item, list(item._items), item.source, item._annotations, item._uid)
                    if hasattr(item, '_items') else (item, None, None, None, None) for item in items]
        retained = {item for item in items if hasattr(item, '_items')}
        for item in old:
            if isinstance(getattr(item, '_content', None), FieldItems):
                item._content.detach(item)
                if item not in retained:
                    item._parent = None
        self.storage = RecordStorage(self.storage.layout.schema)
        self.order = []
        self.handles = self.identities = self.details = _EMPTY_MAP
        self.dirty_fields = self.reordered_fields = 0
        self._records = None
        for item, arguments, source, notes, uid in prepared:
            if arguments is not None:
                item._content = arguments
                item._source, item._annotations, item._uid = source, notes, uid
            self.insert(len(self.order), item)

    def _owned_records(self):
        if self._records is None:
            self._scan_records()
        return self._records

    def _scan_records(self, *, audit=False):
        """Build owned lookups once; a full audit always reads actual order."""
        self._records = None
        groups, ordered = {}, []
        positions = [] if audit else None
        values = self.storage._values
        for item in self.order:
            if isinstance(item, Element):
                groups.setdefault(item.kind, []).append(item)
                ordered.append(item)
            elif isinstance(item, _FieldPosition):
                slot = item.index
                if audit:
                    if type(slot) is not int or not 0 <= slot < len(values):
                        raise ValueError('record field positions do not match stored field order')
                    positions.append(slot)
                if isinstance(values[slot], _Malformed):
                    ordered.append(self.field(slot))
            elif not isinstance(item, Value):
                raise TypeError('record content must contain fields, arguments or owned elements')
        if audit and positions != self.storage._order:
            raise ValueError('record field positions do not match stored field order')
        self._records = ({**{name: tuple(rows) for name, rows in groups.items()}, None: tuple(ordered)}
                         if ordered else _NO_RECORDS)

    def record_children(self):
        return self._owned_records()[None]

    def children(self, kind=None):
        self._owned_records()
        if kind is not None:
            slot = self.storage.layout.slots.get(kind)
            present = slot is not None and self.storage._values[slot] is not MISSING
            owned = self._records.get(kind, ())
            if not present:
                return owned
            if not owned:
                return (self.field(slot),)
            # An invalid duplicate must remain visible to the normal audit,
            # with the same mixed-content order as the public field view.
            return tuple(self.field(item.index) if isinstance(item, _FieldPosition) else item
                         for item in self.order if isinstance(item, _FieldPosition) and item.index == slot
                         or isinstance(item, Element) and item.kind == kind)
        return tuple(item for item in self if isinstance(item, Element) and (kind is None or item.kind == kind))

    def argument(self, slot, index=0):
        """Project a stored argument without creating a leaf element."""
        value = self.storage._values[slot]
        if isinstance(value, _Malformed):
            return value.items[index]
        values = value if self.storage.layout.definitions[slot].kind == 'tuple' else (value,)
        actual = values[index]
        if index < 0:
            index += len(values)
        detail = self.details.get(slot)
        metadata = detail.arguments[index] if detail is not None and index < len(detail.arguments) else None
        return Value(actual, *metadata) if metadata is not None else Value.of(actual)

    def value(self, name):
        slot = self.storage.layout.slots.get(name)
        value = self.storage._values[slot] if slot is not None else MISSING
        return MISSING if isinstance(value, _Malformed) else value

    def invalidate(self):
        self._records = None

    def audit_fields(self, schema, *, proposed=None):
        """Audit a regular value vector once using immutable schema checks.

        Owned field views, malformed content and tuple-valued parameters retain
        the full facade audit. Every call reads current values; no validation
        result or authored availability state is cached. A value-only preview
        overlays the affected slots without expanding the other field handles.
        """
        layout = self.storage.layout
        if layout.schema is not schema:
            return False
        owned = self._owned_records()
        if any(name in schema.fields for name in owned if name is not None):
            return False
        values = self.storage._values
        if layout.tuple_parameters:
            return False
        for name, definition, slot, parameter in layout.field_checks:
            value = values[slot]
            if isinstance(value, _Malformed):
                return False
            if proposed:
                arguments = proposed.get(self.handles.get(slot))
                if arguments is not None:
                    if definition.kind != 'tuple' and len(arguments) != 1:
                        message = 'one named value' if parameter else 'one scalar value'
                        raise ValueError(f'{self.owner.path}: {name} requires {message}')
                    supplied = tuple(argument.value for argument in arguments)
                    value = supplied if definition.kind == 'tuple' else supplied[0]
            if value is MISSING:
                if parameter:
                    raise ValueError(f'{self.owner.path}: {name} requires one named value')
                if definition.required:
                    raise ValueError(f'{self.owner.path}: required field {name} is absent')
            else:
                definition.validate(value)
        return True

    def validate_field(self, name, definition, *, parameter=False):
        """Audit ordinary value slots; unusual structural fields use the facade."""
        if name in self._owned_records():
            return False
        slot = self.storage.layout.slots.get(name)
        value = self.storage._values[slot] if slot is not None else MISSING
        if parameter and definition.readonly:
            return value is MISSING
        if value is MISSING:
            if parameter:
                raise ValueError(f'{self.owner.path}: {name} requires one named value')
            if definition.required:
                raise ValueError(f'{self.owner.path}: required field {name} is absent')
            return True
        if isinstance(value, _Malformed) or parameter and definition.kind == 'tuple':
            return False
        definition.validate(value)
        return True

    def validate(self):
        if self.storage.layout.schema is not self.owner.schema:
            raise ValueError('stored field layout does not match the record schema')
        self.storage._validate_shape()
        # Full audit always sees actual owned content, even after private edits
        # which did not invalidate a previously warmed lookup. The same fresh
        # scan supplies ownership traversal and subsequent schema child checks.
        self._scan_records(audit=True)
        for slot, handle in list(self.handles.items()):
            if (handle._parent is not self.owner or handle.kind != self.storage.layout.names[slot]
                    or type(handle._content) is not FieldItems
                    or handle._content.record is not self or handle._content.slot != slot):
                raise ValueError('inconsistent stored field handle')
            if handle._uid is not None and handle._uid != self.identities.get(slot):
                raise ValueError('stored field identity does not match its live handle')

    def child_kinds(self):
        for item in self.order:
            if isinstance(item, _FieldPosition):
                yield self.storage.layout.names[item.index]
            elif isinstance(item, Element):
                yield item.kind

    def search_children(self, kind):
        for item in self.order:
            if isinstance(item, Element):
                yield item
            elif isinstance(item, _FieldPosition) and (self.storage.layout.names[item.index] == kind
                    or isinstance(self.storage._values[item.index], _Malformed)):
                yield self.field(item.index)

    def materialize(self, node):
        """Keep a field as an ordinary child when its own structure is edited."""
        slot = node._content.slot
        position = self.order.index(self.storage.layout.positions[slot])
        self._remove_field(slot)
        self.order[position] = node
        self._records = None

    def rebind(self, schema):
        if self.storage.layout.schema is schema:
            return
        result = RecordItems(self.owner, schema, retain_debug=self.retain_debug)
        for item in self.order:
            if not isinstance(item, _FieldPosition):
                result.insert(len(result.order), item)
                continue
            slot = item.index
            name = self.storage.layout.names[slot]
            target = result.storage.layout.slots.get(name)
            if (target is None or result.storage.layout.definitions[target].members
                    or name in result.storage):
                node = self.field(slot)
                node._content.detach(node)
                result.order.append(node)
                continue
            value = self.storage._values[slot]
            before, after = self.storage.layout.definitions[slot], result.storage.layout.definitions[target]
            if not isinstance(value, _Malformed) and (before.kind == 'tuple') != (after.kind == 'tuple'):
                if after.kind == 'tuple':
                    value = (value,)
                else:
                    value = value[0] if len(value) == 1 else _Malformed([Value.of(v) for v in value])
            result.storage._store(target, value)
            result.order.append(result.storage.layout.positions[target])
            if slot in self.details:
                if result.details is _EMPTY_MAP:
                    result.details = {}
                result.details[target] = self.details[slot]
            if slot in self.identities:
                result.remember_uid(target, self.identities[slot])
            if self.dirty_fields & (1 << slot):
                result.dirty_fields |= 1 << target
            if self.reordered_fields & (1 << slot):
                result.reordered_fields |= 1 << target
            if (handle := self.handles.get(slot)) is not None:
                result._cache_handle(target, handle)
        self.storage, self.order = result.storage, result.order
        self.handles, self.identities, self.details = result.handles, result.identities, result.details
        self.dirty_fields, self.reordered_fields = result.dirty_fields, result.reordered_fields
        self._records = None
        for slot, handle in list(self.handles.items()):
            handle._content = FieldItems(self, slot)

    def clone_to(self, owner, mapping):
        result = RecordItems(owner, self.storage.layout.schema, retain_debug=self.retain_debug)
        result.storage = self.storage.clone()
        result.dirty_fields, result.reordered_fields = self.dirty_fields, self.reordered_fields
        if self.details:
            result.details = {slot: _Details(detail.source, deepcopy(detail.notes), detail.arguments)
                              for slot, detail in self.details.items()}
        for item in self.order:
            if isinstance(item, Element):
                copied = item._clone(mapping)
                copied._parent = owner
                result.order.append(copied)
            else:
                result.order.append(item)
        if mapping is not None:
            for slot, handle in list(self.handles.items()):
                mapping[handle] = result.field(slot)
        return result
