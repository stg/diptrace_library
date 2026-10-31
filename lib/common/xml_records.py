"""Strict public XML field consumption and exact unit normalization."""
from decimal import Decimal
import re

from .model import Value


MISSING = object()


def application_version(text, *, default):
    """Parse a public XML application version without assigning family policy."""
    text = text.strip()
    if not text:
        return default
    if not re.fullmatch(r'[0-9]+(?:\.[0-9]+){0,3}', text):
        raise ValueError(f'invalid XML application version {text!r}')
    parts = tuple(map(int, text.split('.')))
    return parts+(0,)*(4-len(parts))


class XmlRecord:
    def __init__(self, node):
        self.node = node
        self.used = set()

    def _children(self, name, attribute):
        matches = self.node.children(name)
        if attribute is not None:
            matches = [node for node in matches
                       if (node.annotations.get('xml_role') == 'attribute') == attribute]
        return matches

    def has(self, name, *, attribute=None):
        return bool(self._children(name, attribute))

    def take(self, name, *, required=False, attribute=None):
        """Consume a singleton; specify attribute when XML reuses its name."""
        matches = self._children(name, attribute)
        if len(matches) > 1 or required and not matches:
            raise ValueError(f'{self.node.path}: expected '+('one ' if required else 'at most one ')+name)
        if not matches:
            return None
        self.used.add(matches[0])
        return XmlRecord(matches[0])

    def content(self):
        if len(self.node.arguments) > 1:
            raise ValueError(f'{self.node.path}: expected scalar XML text')
        return self.node.arguments[0] if self.node.arguments else Value.of('')

    def value(self, name, default=MISSING, *, attribute=None):
        child = self.take(name, required=default is MISSING, attribute=attribute)
        if child is None:
            return Value.of(default)
        child.finish(allow_text=True)
        return child.content()

    def text(self, name, default=MISSING, *, attribute=None):
        value = self.value(name, default, attribute=attribute)
        if value.kind != 'string':
            raise ValueError(f'{self.node.path}/{name}: expected text')
        return value.value

    def number(self, name, default=MISSING, *, attribute=None):
        value = self.value(name, default, attribute=attribute)
        if value.kind != 'number' or value.unit:
            raise ValueError(f'{self.node.path}/{name}: expected an unqualified number')
        return value

    def integer(self, name, default=MISSING, *, attribute=None):
        value = self.number(name, default, attribute=attribute).value
        if int(value) != value:
            raise ValueError(f'{self.node.path}/{name}: expected an integer')
        return int(value)

    def boolean(self, name, default=MISSING, *, attribute=None):
        value = self.value(name, default, attribute=attribute)
        if value.kind != 'boolean':
            raise ValueError(f'{self.node.path}/{name}: expected boolean Y or N')
        return value.value

    def rows(self, name, kind):
        # These alternatives name the same public data in different XML
        # dialects. Preserve row order and reject duplicate containers.
        if isinstance(name, str):
            container = self.take(name)
        else:
            matches = [node for node in self.node.children() if node.kind in name]
            if len(matches) > 1:
                raise ValueError(f'{self.node.path}: expected at most one of {name}')
            container = XmlRecord(matches[0]) if matches else None
            self.used.update(matches)
        if container is None:
            return []
        kinds = (kind,) if isinstance(kind, str) else kind
        rows = [node for node in container.node.children() if node.kind in kinds]
        container.used.update(rows)
        container.finish()
        return [XmlRecord(row) for row in rows]

    def children(self, kind):
        rows = self.node.children(kind)
        self.used.update(rows)
        return [XmlRecord(row) for row in rows]

    def finish(self, *, allow_text=False):
        # Formatting whitespace is insignificant in structural records. Scalar
        # readers still consume their literal text through allow_text=True.
        if not allow_text and any(value.kind != 'string' or value.value.strip(' \t\r\n')
                                  for value in self.node.arguments):
            raise ValueError(f'{self.node.path}: unexpected XML text in a record')
        extra = [child.kind for child in self.node.children() if child not in self.used]
        if extra:
            raise ValueError(f'{self.node.path}: unsupported XML fields {extra}')


def enum_value(value, labels, *, negative=None):
    """Resolve labels and equivalent numeric aliases into the current enum."""
    raw = value.value if isinstance(value, Value) else value
    if str(raw) in labels:
        result = labels.index(str(raw))
    else:
        try:
            number = Decimal(str(raw))
            if not number.is_finite() or number != int(number):
                raise ValueError
            result = int(number)
        except (ValueError, ArithmeticError):
            raise ValueError(f'unsupported XML enum {raw!r}; expected one of {labels}') from None
    return -1 if negative is not None and result == labels.index(negative) else result


def length(value, units, *, reverse=False):
    value = value if isinstance(value, Value) else Value.of(value)
    if value.kind != 'number' or value.unit:
        raise ValueError('XML length requires an unqualified number')
    result = units.internal_length(Decimal(str(value.value)))
    if reverse:
        result = result.copy_negate()
    return Value(result, 'number')


def area(value, units):
    """Convert a physical area using the square of the display-length scale."""
    value = value if isinstance(value, Value) else Value.of(value)
    if value.kind != 'number' or value.unit:
        raise ValueError('XML area requires an unqualified number')
    return Value(units.internal_area(Decimal(str(value.value))), 'number')


def point(record, units, names=('X', 'Y'), default=MISSING):
    return tuple(length(record.number(name, default), units, reverse=index == 1)
                 for index, name in enumerate(names))


def replace_rows(owner, name, rows):
    container = owner.one(name)
    for child in list(container.children()):
        child.detach()
    for child in rows:
        container.append(child)
    return container
