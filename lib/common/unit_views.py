"""Lazy measurement views over the same editable records and relationships.

The canonical model owns editing policy. These views only translate declared
quantities at API boundaries; they never change stored units or display settings.
"""
from collections.abc import Iterator, MutableSequence
from dataclasses import fields, replace
from weakref import WeakValueDictionary, ref

from .measurements import LengthUnits
from .model import Document, Element, Value
from .references import (
    References, Reference, UnresolvedReference, Index, Key, Property, Guard,
    OrdinalGuard, Segment,
)
from .refdes import RefDesFamily
from .schema import MISSING
from .structural_edits import preview_structure


_LINK_TYPES = (Reference, UnresolvedReference, Index, Key, Property, Guard, OrdinalGuard, Segment)


def _revalue(original, value):
    if not isinstance(original, Value):
        return value
    if value == original.value and type(value) is type(original.value):
        return original
    return replace(original, value=value, lexeme=None, source=None)


def canonical(value):
    """Reach the authoritative object before calling adapters or algorithms."""
    return value.model if isinstance(value, _View) else value


def in_units(model, units=None):
    selected = LengthUnits(units)
    field = None
    if isinstance(model, _View):
        if model.units == selected.units:
            return model
        field = model._field() if isinstance(model, UnitElement) else None
        model = model.model
    if not isinstance(model, (Document, Element)):
        raise TypeError('measurement views require a document or element')
    owner = model if isinstance(model, Document) else model._owner()
    if owner is not None and owner.representation not in ('tree', *owner._named_representations):
        raise TypeError('measurement views require the editable model, not source syntax')
    result = _Scope(selected).wrap(model)
    if field is not None and isinstance(result, UnitElement) and result._field() is None:
        object.__setattr__(result, '_detached_field', field)
    return result


class _Scope:
    def __init__(self, measurement):
        self.measurement = measurement
        self.objects = WeakValueDictionary()
        self.origins = {}

    def wrap(self, value):
        if value is None or type(value) in (str, int, float, bool):
            return value
        if isinstance(value, (Element, Document, References, RefDesFamily)):
            if (isinstance(value, Document)
                    and value.representation not in ('tree', *value._named_representations)):
                return value  # Explicit syntax inspection retains the format's own units.
            result = self.objects.get(id(value))
            if result is None:
                cls = UnitElement if isinstance(value, Element) else UnitDocument if isinstance(value, Document) else _Service
                result = cls(value, self)
                self.objects[id(value)] = result
            return result
        if isinstance(value, _LINK_TYPES):
            result = self.objects.get(id(value))
            if result is None:
                values = {field.name: self.wrap(getattr(value, field.name)) for field in fields(value)}
                if isinstance(value, Guard):
                    values['values'] = self.wrap(value.field)._values(value.values)
                result = replace(value, **values)
                self.objects[id(value)] = result
                key, origins = id(result), self.origins
                origins[key] = (ref(result, lambda unused: origins.pop(key, None)), value)
            return result
        if isinstance(value, list):
            return [self.wrap(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self.wrap(item) for item in value)
        if isinstance(value, dict):
            return {self.wrap(key): self.wrap(item) for key, item in value.items()}
        if isinstance(value, Iterator):
            return (self.wrap(item) for item in value)
        return value

    def unwrap(self, value):
        if value is None or type(value) in (str, int, float, bool):
            return value
        if isinstance(value, _View):
            return value.model
        if isinstance(value, _LINK_TYPES):
            # Frozen inspection records retain their exact canonical guards.
            # This is a weak view cache, not an authored fact or source backup.
            anchor = next((getattr(value, name) for name in ('source', 'field', 'start')
                           if isinstance(getattr(value, name, None), _View)), None)
            origin = (anchor._scope if anchor is not None else self).origins.get(id(value))
            if origin is not None and origin[0]() is value:
                return origin[1]
            values = {field.name: self.unwrap(getattr(value, field.name)) for field in fields(value)}
            if isinstance(value, Guard) and isinstance(value.field, UnitElement):
                values['values'] = value.field._values(value.values, to_shared=True)
            return replace(value, **values)
        if isinstance(value, (list, _Sequence)):
            return [self.unwrap(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self.unwrap(item) for item in value)
        if isinstance(value, dict):
            return {self.unwrap(key): self.unwrap(item) for key, item in value.items()}
        return value

    def bounds(self, value):
        if value is None:
            return None
        return replace(value, **{name: self.measurement.from_shared(getattr(value, name))
                                 for name in ('left', 'top', 'right', 'bottom')})


class _View:
    __slots__ = ('_model', '_scope', '__weakref__')

    def __init__(self, model, scope):
        object.__setattr__(self, '_model', model)
        object.__setattr__(self, '_scope', scope)

    @property
    def model(self):
        """The same authoritative object, in canonical units."""
        return self._model

    @property
    def units(self):
        return self._scope.measurement.units

    def in_units(self, units=None):
        return in_units(self, units)

    def __bool__(self):
        return bool(self._model)

    def __setattr__(self, name, value):
        if name.startswith('_') or name in ('model', 'units'):
            raise AttributeError(f'{name} is private or read-only')
        setattr(self._model, name, self._scope.unwrap(value))

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        value = getattr(self._model, name)
        if callable(value):
            def call(*args, **options):
                return self._scope.wrap(value(*self._scope.unwrap(args), **self._scope.unwrap(options)))
            return call
        if name in ('annotations', 'metadata', 'diagnostics'):
            return value
        return self._scope.wrap(value)


class _Service(_View):
    __slots__ = ()

    def __len__(self):
        return len(self._model)

    def __iter__(self):
        return (self._scope.wrap(item) for item in self._model)

    def __contains__(self, value):
        return self._scope.unwrap(value) in self._model

    @property
    def issues(self):
        return _Sequence(self._model.issues, self._scope)


class _Sequence(MutableSequence):
    """An editable service list, keeping its nodes in the caller's unit scope."""
    def __init__(self, values, scope):
        self._values, self._scope = values, scope

    def __len__(self): return len(self._values)
    def __getitem__(self, index): return self._scope.wrap(self._values[index])
    def __setitem__(self, index, value): self._values[index] = self._scope.unwrap(value)
    def __delitem__(self, index): del self._values[index]
    def insert(self, index, value): self._values.insert(index, self._scope.unwrap(value))


class UnitElement(_View):
    """An element facade with declared lengths and areas in selected units."""
    __slots__ = ('_detached_field',)

    def __init__(self, model, scope):
        super().__init__(model, scope)
        object.__setattr__(self, '_detached_field', self._field())

    @property
    def schema(self): return self._model.schema

    @property
    def kind(self): return self._model.kind

    @property
    def uid(self): return self._model.uid

    @property
    def path(self): return self._model.path

    @property
    def parent(self): return self._scope.wrap(self._model.parent)

    def children(self, kind=None): return self._scope.wrap(self._model.children(kind))
    def child(self, kind): return self._scope.wrap(self._model.child(kind))
    def find(self, kind): return self.child(kind)
    def descendants(self, kind=None): return self._scope.wrap(self._model.descendants(kind))
    def walk(self, *, include_self=False): return self._scope.wrap(self._model.walk(include_self=include_self))

    def _field(self):
        parent = self._model.parent
        if parent is not None and parent.schema is not None:
            return parent.schema.fields.get(self._model.kind)
        return getattr(self, '_detached_field', None)

    def _convert(self, definition, value, *, to_shared=False, current=MISSING):
        value = self._scope.unwrap(value) if to_shared else value
        if definition is not None:
            value = self._scope.measurement.field_value(
                definition, value, record=self._model, to_shared=to_shared, current=current)
        return value if to_shared else self._scope.wrap(value)

    def _quantity_record(self):
        return self._model.parent if self._field() is not None and self._model.parent is not None else self._model

    def __getitem__(self, name):
        schema = self._model.schema
        definition = schema.fields.get(name) if schema is not None else None
        return self._convert(definition, self._model[name])

    def get(self, name, default=None):
        try:
            return self[name]
        except KeyError:
            return default

    def set(self, name, value):
        definition = self.schema.fields[name] if self.schema is not None else None
        converted = self._convert(definition, value, to_shared=True, current=self._model.get(name, MISSING))
        self._model.set(name, converted)

    def __setitem__(self, name, value): self.set(name, value)
    def __delitem__(self, name): del self._model[name]
    def __contains__(self, name): return name in self._model

    def scalar(self, name, default=None, *, occurrence=0):
        value = self._model.scalar(name, MISSING, occurrence=occurrence)
        if value is MISSING:
            return default
        definition = self.schema.fields.get(name) if self.schema is not None else None
        return self._convert(definition, value)

    def _argument_definition(self, index):
        definition = self._field()
        if definition is not None:
            if definition.kind == 'tuple':
                return definition.members[index] if definition.members else definition
            return definition if index == 0 else None
        if self.schema is not None and index < len(self.schema.parameters):
            definition = self.schema.fields[self.schema.parameters[index]]
            return definition.members[0] if definition.kind == 'tuple' and definition.members else definition
        return None

    def _values(self, values, *, to_shared=False):
        current = self._model.values
        result = []
        for index, value in enumerate(values):
            definition = self._argument_definition(index)
            if definition is not None:
                value = self._scope.measurement._field_scalar(
                    definition, value, record=self._quantity_record(), to_shared=to_shared,
                    current=current[index] if to_shared and index < len(current) else MISSING)
            result.append(value)
        return tuple(result)

    @property
    def values(self):
        return self._values(self._model.values)

    @property
    def arguments(self):
        return tuple(_revalue(argument, value)
                     for argument, value in zip(self._model.arguments, self.values))

    @property
    def items(self):
        offset = len(self.schema.parameters) if self.schema is not None else 0
        arguments, result = self.arguments, []
        for item in self._model.items:
            if isinstance(item, Value):
                result.append(arguments[offset])
                offset += 1
            else:
                result.append(self._scope.wrap(item))
        return tuple(result)

    def _argument(self, index, value):
        supplied = value.value if isinstance(value, Value) else value
        current = self._model.arguments
        if index < 0:
            index += len(current)
        if index < 0:
            raise IndexError(index)
        definition = self._argument_definition(index)
        if definition is not None:
            supplied = self._scope.measurement._field_scalar(
                definition, supplied, record=self._quantity_record(), to_shared=True,
                current=current[index].value if index < len(current) else MISSING)
        return _revalue(value, supplied)

    def set_argument(self, index, value):
        self._model.set_argument(index, self._argument(index, value))
        return self

    def set_values(self, *values):
        converted = tuple(self._argument(index, value) for index, value in enumerate(values))
        self._model.set_values(*converted)
        return self

    def set_field(self, name, *values, occurrence=0):
        definition = self.schema.fields.get(name) if self.schema is not None else None
        if definition is not None:
            scalars = tuple(value.value if isinstance(value, Value) else value for value in values)
            value = scalars if definition.kind == 'tuple' else scalars[0] if len(scalars) == 1 else scalars
            converted = self._convert(definition, value, to_shared=True, current=self._model.scalar(name, MISSING, occurrence=occurrence))
            converted = converted if definition.kind == 'tuple' else (converted,)
            values = tuple(_revalue(original, value) for original, value in zip(values, converted, strict=True))
        return self._scope.wrap(self._model.set_field(name, *values, occurrence=occurrence))

    def select(self, path, *, where=None):
        from .query import select
        return select(self, path, where=where)

    def one(self, path, *, where=None):
        matches = self.select(path, where=where)
        if len(matches) != 1:
            raise LookupError(f'expected one match for {path!r}, found {len(matches)}')
        return matches[0]

    def find_all(self, kind=None, *, recursive=False, where=None):
        from .query import filter_matches
        nodes = self.descendants(kind) if recursive else self.children(kind)
        return filter_matches(nodes, where)

    def add(self, kind, *values):
        field = self.schema.fields.get(kind) if self.schema is not None else None
        if field is not None:
            supplied = tuple(value.value if isinstance(value, Value) else value for value in values)
            value = supplied if field.kind == 'tuple' else supplied[0] if len(supplied) == 1 else supplied
            converted = self._convert(field, value, to_shared=True)
            converted = converted if field.kind == 'tuple' else (converted,)
            arguments = tuple(_revalue(original, value) for original, value in zip(values, converted, strict=True))
            return self._scope.wrap(self._model.append(Element(kind, *arguments)))
        candidate = Element(kind, *values)
        owner = self._model._owner()
        with preview_structure({}, {candidate: self._model}, {}):
            schema = owner._record_definition(candidate) if owner is not None else None
        if values and schema is None:
            raise TypeError('new measurement-view arguments require an owning record schema')
        if schema is not None:
            converted = []
            for index, value in enumerate(values):
                supplied = value.value if isinstance(value, Value) else value
                if index < len(schema.parameters):
                    definition = schema.fields[schema.parameters[index]]
                    supplied = self._scope.measurement.field_value(definition, supplied, record=candidate, to_shared=True)
                converted.append(_revalue(value, supplied))
            candidate = Element(kind, *converted)
        return self._scope.wrap(self._model.append(candidate))

    def clone(self):
        result = self._scope.wrap(self._model.clone())
        if result._field() is None:
            object.__setattr__(result, '_detached_field', self._field())
        return result

    def inspect(self):
        result = self._model.inspect()
        result['values'] = [dict(value=value.value, kind=value.kind, unit=value.unit, source=value.source)
                            for value in self.arguments]
        result['units'] = self.units
        return result


class UnitDocument(_View):
    """A document facade whose selections and edits use one length preference."""
    __slots__ = ()

    @property
    def root(self): return self._scope.wrap(self._model.root)

    @property
    def references(self): return self._scope.wrap(self._model.references)

    def select(self, path, *, where=None):
        return self.root.select(path, where=where)

    def one(self, path, *, where=None):
        return self.root.one(path, where=where)

    def find_all(self, kind, *, where=None):
        return self.root.find_all(kind, recursive=True, where=where)

    def copy(self, node, *, parent=None, index=None, fields=None):
        source = self._scope.wrap(canonical(node))
        converted = None if fields is None else {
            name: source._convert(source.schema.fields[name], value, to_shared=True,
                                  current=source.model.get(name, MISSING))
            for name, value in fields.items()}
        return self._scope.wrap(self._model.copy(canonical(node), parent=canonical(parent), index=index, fields=converted))
