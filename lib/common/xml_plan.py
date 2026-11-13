"""Immutable XML projection facts, materialized only when they are emitted.

These records are destination data, not editable design objects. Attributes
have their own typed storage instead of requiring one Element per attribute.
"""
from dataclasses import dataclass, replace

from .model import Element, Value, _valid_element_name


def _key(values):
    return tuple((value.kind, value.value, value.unit) for value in values)


@dataclass(frozen=True, slots=True)
class XmlPlan:
    kind: str
    arguments: tuple = ()
    attributes: tuple = ()
    children: tuple = ()

    @classmethod
    def from_element(cls, element):
        """Snapshot generated XML data without retaining its editable tree."""
        from .xml import syntax_role

        def snapshot(node):
            if syntax_role(node) is not None:
                raise ValueError('XML plans require ordinary element content')
            attributes, children = [], []
            arguments = []
            for child in node._items:
                if isinstance(child, Value):
                    if children:
                        raise ValueError('XML plans cannot reorder mixed element/text content')
                    arguments.append(child)
                    continue
                if syntax_role(child) == 'attribute':
                    if len(child.arguments) != 1 or child.children():
                        raise ValueError('XML plan attributes require one scalar value')
                    attributes.append((child.kind, child.arguments[0]))
                else:
                    children.append(snapshot(child))
            return cls(node.kind, tuple(arguments), tuple(attributes), tuple(children))
        return snapshot(element)

    def child(self, name):
        return next((child for child in self.children if child.kind == name), None)

    def with_child(self, original, replacement):
        """Replace one exact owned plan; preserve all other data and ordering."""
        if not any(child is original for child in self.children):
            raise ValueError('replacement requires an owned XML plan')
        return replace(self, children=tuple(replacement if child is original else child for child in self.children))

    def without_fields(self, names):
        """Exclude selected root attributes/children from a comparison view."""
        return replace(self, attributes=tuple((name, value) for name, value in self.attributes if name not in names),
                       children=tuple(child for child in self.children if child.kind not in names))

    def key(self, *, omit_attribute=None):
        """Use the same complete semantic key as an editable XML projection."""
        attributes = tuple(sorted((name, _key((value,))) for name, value in self.attributes
                                  if name != omit_attribute))
        return self.kind, _key(self.arguments), attributes, tuple(child.key() for child in self.children)

    def attribute(self, name):
        for key, value in self.attributes:
            if key == name:
                return value.value
        raise KeyError(name)

    def with_attribute(self, name, value):
        if not _valid_element_name(name):
            raise ValueError('invalid XML attribute name: '+repr(name))
        value = Value.of(value)
        attributes = dict(self.attributes)
        attributes[name] = value
        return replace(self, attributes=tuple(attributes.items()))

    def element(self):
        """Build a detached ordinary XML tree for public inspection/serialization."""
        node = Element(self.kind, *self.arguments)
        for name, value in self.attributes:
            field = Element(name, value)
            field.annotations['xml_role'] = 'attribute'
            node._append_import(field)
        for child in self.children:
            node._append_import(child.element())
        return node


class XmlBuilder:
    """Small mutable construction phase for a detached immutable plan."""
    __slots__ = ('kind', 'arguments', 'attributes', 'children')

    def __init__(self, kind, *values):
        if not _valid_element_name(kind):
            raise ValueError('invalid XML element name: '+repr(kind))
        self.kind = kind
        self.arguments = tuple(Value.of(value) for value in values)
        self.attributes, self.children = {}, []

    def attribute(self, name, supplied):
        value = Value.of(supplied)
        previous = self.attributes.get(name)
        if (previous is None or
                (previous.value, previous.kind, previous.unit) != (value.value, value.kind, value.unit)
                or isinstance(supplied, Value) and previous != value):
            self.attributes[name] = value

    def add(self, kind, *values):
        node = type(self)(kind, *values)
        self.children.append(node)
        return node

    def append(self, node):
        if not isinstance(node, (XmlBuilder, XmlPlan)):
            raise TypeError('XML plans require builder or frozen plan children')
        self.children.append(node)
        return node

    def freeze(self):
        return XmlPlan(self.kind, self.arguments, tuple(self.attributes.items()),
                       tuple(child if isinstance(child, XmlPlan) else child.freeze()
                             for child in self.children))
