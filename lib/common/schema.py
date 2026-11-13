"""Immutable record definitions shared by editing, reflection and documentation."""
from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field, replace
from decimal import Decimal
import math
from types import MappingProxyType
from typing import Callable, Mapping


MISSING = object()
_in_validation_preview = lambda: False
_in_structure_preview = lambda: False
_validation_values = lambda: None


def _validate_tuple_scalars(values, name):
    """Check untyped tuple payloads without allocating member definitions."""
    for value in values:
        if value is None or isinstance(value, (str, bool, int)):
            continue
        if isinstance(value, tuple):
            _validate_tuple_scalars(value, name)
        elif isinstance(value, (float, Decimal)):
            if not math.isfinite(float(value)):
                raise ValueError(f'{name} requires finite floating numbers')
        else:
            raise TypeError(f'{name} tuple values must be scalars')


def _bind_validation_preview(guard, *, structure, values):
    """Bind model preview state after the shared types have been initialized."""
    global _in_validation_preview, _in_structure_preview, _validation_values
    _in_validation_preview = guard
    _in_structure_preview, _validation_values = structure, values


@dataclass(frozen=True)
class Field:
    name: str
    kind: str = 'value'
    required: bool = False
    nullable: bool = False
    default: object = MISSING
    unit: str = ''
    description: str = ''
    getter: Callable | None = None
    setter: Callable | None = None
    members: tuple[Field, ...] = ()
    item_kind: str = ''
    length: int | None = None
    ordinal_dependencies: Callable | None = None
    reference_dependencies: Callable | None = None
    collection_dependencies: Callable | None = None
    value_dependencies: Callable | None = None
    choices: tuple = ()
    unit_sentinels: tuple = ()
    unit_selector: Callable | None = None
    _item_definition: object = dataclass_field(init=False, repr=False, compare=False, default=None)
    _stores_integer: bool = dataclass_field(init=False, repr=False, compare=False, default=False)

    def __post_init__(self):
        object.__setattr__(self, 'choices', tuple(self.choices))
        object.__setattr__(self, 'unit_sentinels', tuple(self.unit_sentinels))
        if not isinstance(self.unit, str):
            raise TypeError('field units must be text')
        if self.unit_selector is not None and not callable(self.unit_selector):
            raise TypeError('a field unit selector must be callable or None')
        kinds = self.kind.split('|')
        object.__setattr__(self, '_stores_integer',
                           'integer' in kinds and not {'number', 'value'}.intersection(kinds))
        if (self.item_kind or self.length is not None) and self.kind != 'tuple':
            raise ValueError('tuple item types and lengths require a tuple field')
        if self.length is not None and (isinstance(self.length, bool) or
                not isinstance(self.length, int) or self.length < 0):
            raise ValueError('tuple length requires a nonnegative integer')
        if self.members and self.length is not None and len(self.members) != self.length:
            raise ValueError('tuple length must agree with its named members')
        if self.item_kind:
            object.__setattr__(self, '_item_definition', Field(self.name+' item', self.item_kind))

    @property
    def readonly(self):
        return self.getter is not None and self.setter is None

    def validate(self, value):
        if self.readonly:
            raise TypeError(f'{self.name} is calculated and cannot be assigned')
        if value is None:
            if self.nullable:
                return
            raise TypeError(f'{self.name} does not accept None; remove an optional field explicitly')
        # Most stored fields use these built-in scalar types. Their valid
        # cases need neither numeric coercion nor tuple/union dispatch. Keep
        # subclasses, choices and all failures on the complete checks below.
        if not self.choices:
            value_type, kind = type(value), self.kind
            if ((value_type is str and kind in ('text', 'value'))
                    or (value_type is bool and kind in ('boolean', 'value'))
                    or (value_type is int and kind in ('integer', 'number', 'value'))
                    or (value_type is float and kind in ('number', 'value') and math.isfinite(value))
                    or (value_type is Decimal and kind in ('number', 'value')
                        and value.is_finite() and math.isfinite(float(value)))):
                return
        if '|' in self.kind:
            for kind in self.kind.split('|'):
                try:
                    replace(self, kind=kind).validate(value)
                except TypeError:
                    continue
                return
            raise TypeError(f'{self.name} requires {self.kind}')
        if self.kind == 'reference':
            from .model import Element
            if not isinstance(value, Element):
                raise TypeError(f'{self.name} requires an Element reference')
            return
        numeric = isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)
        if numeric and ((isinstance(value, float) and not math.isfinite(value)) or
                        (isinstance(value, Decimal) and (not value.is_finite() or
                         self.kind in ('number', 'value') and not math.isfinite(float(value))))):
            raise ValueError(f'{self.name} requires a finite number')
        if self.kind == 'text':
            valid = isinstance(value, str)
        elif self.kind == 'boolean':
            valid = isinstance(value, bool)
        elif self.kind == 'number':
            valid = numeric
        elif self.kind == 'integer':
            valid = numeric and value == int(value)
        elif self.kind == 'tuple':
            valid = isinstance(value, tuple)
        elif self.kind == 'value':
            valid = isinstance(value, (str, bool, int, float, Decimal))
        else:
            raise ValueError(f'unknown schema field type: {self.kind}')
        if not valid:
            raise TypeError(f'{self.name} requires {self.kind}')
        if self.choices and value not in self.choices:
            raise ValueError(f'{self.name} must be one of {self.choices}')
        if self.kind == 'tuple' and self.length is not None and len(value) != self.length:
            raise ValueError(f'{self.name} requires {self.length} tuple values')
        if self.kind == 'tuple' and self.item_kind:
            for item in value:
                self._item_definition.validate(item)
        if self.kind == 'tuple' and self.members:
            if len(value) != len(self.members):
                raise ValueError(f'{self.name} requires {len(self.members)} named tuple members')
            for member, item in zip(self.members, value):
                member.validate(item)
        elif self.kind == 'tuple' and not self.item_kind:
            _validate_tuple_scalars(value, self.name)


def with_units(record, units, *, sentinels=None, selectors=None):
    """Declare measurement metadata alongside a record's field vocabulary.

    Returned definitions remain immutable. Sentinels and selectors describe
    existing value domains; they neither add design facts nor change validation.
    """
    sentinels, selectors = sentinels or {}, selectors or {}
    unknown = (units.keys() | sentinels.keys() | selectors.keys()) - record.fields.keys()
    if unknown:
        raise KeyError(f'{record.name}: unknown unit fields {sorted(unknown)!r}')
    fields = dict(record.fields)
    for name in units.keys() | sentinels.keys() | selectors.keys():
        field = fields[name]
        fields[name] = replace(field, unit=units.get(name, field.unit),
                               unit_sentinels=sentinels.get(name, field.unit_sentinels),
                               unit_selector=selectors.get(name, field.unit_selector))
    return replace(record, fields=fields)


@dataclass(frozen=True)
class Child:
    """An owned record or ordered collection, separate from scalar fields."""
    name: str
    record: str = ''
    minimum: int = 0
    maximum: int | None = 1
    description: str = ''

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name:
            raise ValueError('child definitions require a name')
        if not isinstance(self.record, str):
            raise TypeError('child record definition names require text')
        if isinstance(self.minimum, bool) or not isinstance(self.minimum, int) or self.minimum < 0:
            raise ValueError('minimum child count requires a nonnegative integer')
        if self.maximum is not None and (isinstance(self.maximum, bool) or
                not isinstance(self.maximum, int) or self.maximum < self.minimum):
            raise ValueError('maximum child count must be at least its minimum')


@dataclass(frozen=True)
class Record:
    name: str
    fields: Mapping[str, Field]
    parameters: tuple[str, ...] = ()
    description: str = ''
    children: Mapping[str, Child] = dataclass_field(default_factory=dict)

    def __post_init__(self):
        fields = dict(self.fields)
        if any(name != definition.name for name, definition in fields.items()):
            raise ValueError('record field names must match their definitions')
        if any(name not in fields for name in self.parameters):
            raise ValueError('every positional adapter parameter needs a named field')
        children = dict(self.children)
        if any(name != definition.name for name, definition in children.items()):
            raise ValueError('child names must match their definitions')
        if fields.keys() & children.keys():
            raise ValueError('scalar fields and owned children must have distinct names')
        object.__setattr__(self, 'fields', MappingProxyType(fields))
        object.__setattr__(self, 'children', MappingProxyType(children))

    def field(self, name):
        return self.fields[name]

    def validate_children(self, record):
        for name, definition in self.children.items():
            children = record._child_sequence(name)
            count = len(children)
            if count < definition.minimum or definition.maximum is not None and count > definition.maximum:
                maximum = 'unbounded' if definition.maximum is None else definition.maximum
                raise ValueError(f'{record.path}: {name} requires {definition.minimum}..{maximum} children; found {count}')
            if definition.record:
                for child in children:
                    if child.schema is not None and child.schema.name not in definition.record.split('|'):
                        raise ValueError(f'{child.path}: expected {definition.record}, found {child.schema.name}')

    def validate_parameters(self, record):
        direct = None if _in_validation_preview() else getattr(record._content, 'validate_field', None)
        for name in self.parameters:
            definition = self.fields[name]
            if direct is not None and direct(name, definition, parameter=True):
                continue
            children = record._child_sequence(name)
            if definition.readonly:
                if children:
                    raise ValueError(f'{name} is calculated and must not have a stored duplicate')
                continue
            if len(children) != 1 or children[0]._child_sequence():
                raise ValueError(f'{record.path}: {name} requires one named value')
            arguments = children[0].arguments
            if len(arguments) != 1:
                raise ValueError(f'{record.path}: {name} requires one named value')
            definition.validate(arguments[0].value)

    def validate_fields(self, record):
        """Audit present stored values and required fields without reading unresolved getters."""
        bulk = (None if type(self) is not Record or _in_structure_preview()
                else getattr(record._content, 'audit_fields', None))
        if bulk is not None and bulk(self, proposed=_validation_values()):
            return
        self.validate_parameters(record)
        direct = None if _in_validation_preview() else getattr(record._content, 'validate_field', None)
        for name, definition in self.fields.items():
            if name in self.parameters or definition.getter is not None:
                continue
            if direct is not None and direct(name, definition):
                continue
            children = record._child_sequence(name)
            if not children:
                if definition.required:
                    raise ValueError(f'{record.path}: required field {name} is absent')
                continue
            if len(children) != 1:
                raise ValueError(f'{record.path}: field {name} occurs more than once')
            child = children[0]
            arguments = child.arguments
            if definition.kind != 'tuple' and len(arguments) != 1:
                raise ValueError(f'{record.path}: {name} requires one scalar value')
            if definition.kind != 'tuple' and child._child_sequence():
                raise TypeError(f'{record.path}: {name} is a container, not a scalar field')
            values = tuple(argument.value for argument in arguments)
            definition.validate(values if definition.kind == 'tuple' else values[0])
