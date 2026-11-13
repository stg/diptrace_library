"""Compact named values behind record and field views.

This private storage layer owns values, not editing policy or relationships.
Document edits must still preflight their constraints before committing here.
Owned records and syntax/provenance have separate storage responsibilities.
"""
from decimal import Decimal
from dataclasses import dataclass, field
import math
from types import MappingProxyType

from .schema import MISSING


@dataclass(frozen=True, slots=True)
class _FieldPosition:
    index: int


@dataclass(frozen=True, slots=True)
class RecordLayout:
    """One shared name-to-slot map for an immutable record definition."""
    schema: object
    names: tuple = field(init=False)
    definitions: tuple = field(init=False)
    slots: object = field(init=False)
    positions: tuple = field(init=False, repr=False)
    field_checks: tuple = field(init=False, repr=False)
    tuple_parameters: bool = field(init=False, repr=False)

    def __post_init__(self):
        names = tuple(name for name, definition in self.schema.fields.items() if definition.getter is None)
        object.__setattr__(self, 'names', names)
        object.__setattr__(self, 'definitions', tuple(self.schema.fields[name] for name in names))
        object.__setattr__(self, 'slots', MappingProxyType({name: index for index, name in enumerate(names)}))
        object.__setattr__(self, 'positions', tuple(_FieldPosition(index) for index in range(len(names))))
        check_names = (*self.schema.parameters, *(name for name in names if name not in self.schema.parameters))
        object.__setattr__(self, 'field_checks', tuple(
            (name, self.schema.fields[name], self.slots[name], name in self.schema.parameters)
            for name in check_names if name in self.slots))
        object.__setattr__(self, 'tuple_parameters', any(
            self.schema.fields[name].kind == 'tuple' for name in self.schema.parameters))

    @classmethod
    def for_schema(cls, schema):
        layout = getattr(schema, '_value_layout', None)
        if layout is None:
            layout = cls(schema)
            # This derived private cache does not change the immutable schema.
            object.__setattr__(schema, '_value_layout', layout)
        return layout

    def slot(self, name):
        field = self.schema.fields[name]
        if field.getter is not None:
            raise TypeError(f'{name} is calculated and has no stored value')
        return self.slots[name]


def _scalar(value):
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, (float, Decimal)):
        if not (math.isfinite(value) if isinstance(value, float) else value.is_finite()):
            raise ValueError('stored numbers must be finite')
        return
    raise TypeError(f'unsupported stored value: {type(value).__name__}')


def _validate_value(value):
    if isinstance(value, tuple):
        for item in value:
            _validate_value(item)
    else:
        _scalar(value)


def _value(value, definition=None):
    """Store ordinary numeric facts with Python's floating-point arithmetic."""
    if isinstance(value, tuple):
        members = definition.members if definition is not None else ()
        if members and len(members) == len(value):
            return tuple(_value(item, member) for item, member in zip(value, members))
        if definition is not None and definition._item_definition is not None:
            return tuple(_value(item, definition._item_definition) for item in value)
        return tuple(_value(item) for item in value)
    _scalar(value)
    if (definition is not None and definition._stores_integer
            and isinstance(value, (float, Decimal))):
        integral = int(value)
        if value != integral:
            raise TypeError(f'{definition.name} requires an integer')
        return integral
    if isinstance(value, Decimal):
        value = float(value)
        if not math.isfinite(value):
            raise ValueError('stored numbers must be finite')
    return value


class FieldHandle:
    """A retained address follows edits, but never aliases a recreated field.

    Removing a field detaches existing handles with their current value. That
    value then belongs to the detached handle, as with a detached tree element.
    """
    __slots__ = ('_storage', '_slot', '_definition', '_detached')

    def __init__(self, storage, slot):
        self._storage = storage
        self._slot = slot
        self._definition = storage.layout.definitions[slot]
        self._detached = MISSING

    @property
    def name(self):
        return self._definition.name

    @property
    def attached(self):
        return self._storage is not None

    @property
    def value(self):
        if self._storage is None:
            return self._detached
        return self._storage._values[self._slot]

    @value.setter
    def value(self, value):
        if self._storage is not None:
            self._storage[self.name] = value
        else:
            self._definition.validate(value)
            self._detached = _value(value, self._definition)

    def _detach(self, value):
        self._storage = None
        self._detached = value


class RecordStorage:
    """A value vector with explicit absence and lazily materialized handles.

    Schema defaults do not imply presence. Values are authoritative here; live
    handles are addresses rather than copies of those values. Slot order is
    shared, while the insertion order of present fields belongs to each record.
    """
    __slots__ = ('layout', '_values', '_order', '_handles')

    def __init__(self, schema, values=None):
        self.layout = RecordLayout.for_schema(schema)
        self._values = [MISSING] * len(self.layout.names)
        self._order = []
        self._handles = None
        if values:
            self.update(values)

    def __len__(self):
        return len(self._order)

    def __contains__(self, name):
        index = self.layout.slots.get(name)
        return index is not None and self._values[index] is not MISSING

    def __getitem__(self, name):
        value = self._values[self.layout.slot(name)]
        if value is MISSING:
            raise KeyError(name)
        return value

    def get(self, name, default=None):
        if name not in self.layout.slots:
            return default
        value = self._values[self.layout.slots[name]]
        return default if value is MISSING else value

    def __setitem__(self, name, value):
        slot = self.layout.slot(name)
        self.layout.definitions[slot].validate(value)
        self._store(slot, _value(value, self.layout.definitions[slot]))

    def _store(self, slot, value):
        # Readers may construct scalar slots without Value objects. Normalize
        # those values here too; strings, identities and malformed diagnostics
        # keep their own representations.
        if (isinstance(value, (Decimal, tuple)) or isinstance(value, float)
                and self.layout.definitions[slot]._stores_integer):
            value = _value(value, self.layout.definitions[slot])
        if self._values[slot] is MISSING:
            self._order.append(slot)
        self._values[slot] = value

    def update(self, values):
        # Prepare the entire group so a rejected field changes nothing.
        prepared = []
        for name, value in values.items():
            slot = self.layout.slot(name)
            self.layout.definitions[slot].validate(value)
            prepared.append((slot, _value(value, self.layout.definitions[slot])))
        for slot, value in prepared:
            self._store(slot, value)

    def pop(self, name):
        slot = self.layout.slot(name)
        value = self[name]
        if self.layout.definitions[slot].required:
            raise TypeError(f'{name} is required and cannot be removed')
        if self._handles is not None:
            handle = self._handles.pop(slot, None)
            if handle is not None:
                handle._detach(value)
        self._values[slot] = MISSING
        self._order.remove(slot)
        return value

    def field(self, name):
        slot = self.layout.slot(name)
        if self._values[slot] is MISSING:
            raise KeyError(name)
        if self._handles is None:
            self._handles = {}
        handle = self._handles.get(slot)
        if handle is None:
            handle = self._handles[slot] = FieldHandle(self, slot)
        return handle

    def attach(self, handle):
        if not isinstance(handle, FieldHandle) or handle.attached:
            raise ValueError('field handle must be detached before attachment')
        slot = self.layout.slot(handle.name)
        if self._values[slot] is not MISSING:
            raise ValueError(f'{handle.name} already has a stored value')
        self.layout.definitions[slot].validate(handle.value)
        value = _value(handle.value, self.layout.definitions[slot])
        self._store(slot, value)
        handle._storage, handle._slot = self, slot
        handle._definition = self.layout.definitions[slot]
        handle._detached = MISSING
        if self._handles is None:
            self._handles = {}
        self._handles[slot] = handle

    def items(self):
        return ((self.layout.names[slot], self._values[slot]) for slot in self._order)

    def clone(self):
        result = RecordStorage(self.layout.schema)
        result._values = self._values.copy()
        result._order = self._order.copy()
        return result

    def _validate_shape(self):
        size = len(self.layout.names)
        if len(self._values) != size:
            raise ValueError('stored value count does not match the record schema')
        if (any(type(slot) is not int or not 0 <= slot < size for slot in self._order)
                or len(set(self._order)) != len(self._order)
                or set(self._order) != {i for i, value in enumerate(self._values) if value is not MISSING}):
            raise ValueError('stored field order does not match field presence')

    def validate(self):
        """Audit actual storage, including corruption behind existing handles."""
        self._validate_shape()
        size = len(self.layout.names)
        for slot, definition in enumerate(self.layout.definitions):
            value = self._values[slot]
            if value is MISSING:
                if definition.required:
                    raise ValueError(f'required field {definition.name} is absent')
            else:
                definition.validate(value)
                _validate_value(value)
        for slot, handle in (self._handles or {}).items():
            if (type(slot) is not int or not 0 <= slot < size or self._values[slot] is MISSING
                    or handle._storage is not self or handle._slot != slot
                    or handle._definition is not self.layout.definitions[slot]):
                raise ValueError('field handle does not address its current stored value')
