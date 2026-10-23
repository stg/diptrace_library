"""Our editable document tree, independent of any binary serializer or layout.

An element contains an ordered mixture of values and child elements. This
retains duplicate fields, tuple arguments, empty containers and ordering without
forcing a source format's private object layout onto the public API.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import math
import re
from typing import Callable, Iterator
from uuid import uuid4
from .conversion import export_diagnostics, import_diagnostics


Scalar = str | int | Decimal | bool
ELEMENT_NAME = r"[A-Za-z_][A-Za-z_0-9.-]*"
_NAME = re.compile(ELEMENT_NAME + r"\Z")
_SYMBOL = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z")


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
    def __init__(self, kind: str, *values: Scalar | float | Value, source: SourceSpan | None = None):
        if kind and not _NAME.fullmatch(kind):
            raise ValueError(f"invalid element kind: {kind!r}")
        self._uid = uuid4().hex
        self._kind = kind
        self._items: list[Element | Value] = [Value.of(v) for v in values]
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
        if not _NAME.fullmatch(kind):
            raise ValueError(f"invalid element kind: {kind!r}")
        if self._kind != kind:
            self._kind = kind
            self._touch()

    @property
    def type(self) -> str:
        """Familiar query vocabulary from the earlier library API."""
        return self.kind

    @property
    def parent(self) -> "Element | None":
        return self._parent

    @property
    def changed(self) -> bool:
        """Whether this element or any descendant changed since loading."""
        return self._dirty

    @property
    def items(self) -> tuple["Element | Value", ...]:
        return tuple(self._items)

    @property
    def arguments(self) -> tuple[Value, ...]:
        return tuple(i for i in self._items if isinstance(i, Value))

    @property
    def values(self) -> tuple[Scalar, ...]:
        return tuple(v.value for v in self.arguments)

    @property
    def path(self) -> str:
        parts = []
        node = self
        while node.parent is not None:
            peers = node.parent.children(node.kind)
            parts.append(f"{node.kind}[{peers.index(node)+1}]")
            node = node.parent
        return "/" + "/".join(reversed(parts))

    def _touch(self, *, reordered=False):
        self._reordered |= reordered
        node: Element | None = self
        while node is not None:
            node._dirty = True
            node = node.parent

    def children(self, kind: str | None = None) -> list["Element"]:
        return [i for i in self._items if isinstance(i, Element) and (kind is None or i.kind == kind)]

    def child(self, kind: str) -> "Element | None":
        return next(iter(self.children(kind)), None)

    def find(self, kind: str) -> "Element | None":
        return self.child(kind)

    def find_all(self, kind: str | None = None, *, recursive=False,
                 where: Callable[["Element"], bool] | None = None) -> list["Element"]:
        nodes = self.descendants(kind) if recursive else self.children(kind)
        return [n for n in nodes if where is None or where(n)]

    def walk(self, *, include_self=False) -> Iterator["Element"]:
        stack = [self] if include_self else list(reversed(self.children()))
        while stack:
            node = stack.pop()
            yield node
            stack.extend(reversed(node.children()))

    def descendants(self, kind: str | None = None) -> list["Element"]:
        return [n for n in self.walk() if kind is None or n.kind == kind]

    def select(self, path: str) -> list["Element"]:
        from .query import select
        return select(self, path)

    def one(self, path: str) -> "Element":
        matches = self.select(path)
        if len(matches) != 1:
            raise LookupError(f"expected one match for {path!r}, found {len(matches)}")
        return matches[0]

    def scalar(self, name: str, default=None, *, occurrence=0):
        matches = self.children(name)
        if occurrence >= len(matches):
            return default
        node = matches[occurrence]
        if node.children():
            raise ValueError(f"{node.path} is a container, not a scalar field")
        return node.values[0] if len(node.values) == 1 else node.values

    def set_argument(self, index: int, value: Scalar | float | Value) -> "Element":
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
            if node.children():
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
        children = self.children()
        if index is None:
            index = len(children)
        if not 0 <= index <= len(children):
            raise IndexError(index)
        position = self._items.index(children[index]) if index < len(children) else len(self._items)
        self._items.insert(position, node)
        node._parent = self
        self._touch(reordered=True)
        return node

    def append(self, node: "Element") -> "Element":
        return self.insert(node)

    def add(self, kind: str, *values: Scalar | float | Value) -> "Element":
        return self.append(Element(kind, *values))

    def detach(self) -> "Element":
        if self.parent is not None:
            parent = self.parent
            parent._items.remove(self)
            self._parent = None
            parent._touch(reordered=True)
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
        self.detach()
        return parent.insert(self, index)

    def clone(self) -> "Element":
        """Copy content and formatting with fresh identities and no shared children."""
        from copy import deepcopy
        result = Element(self.kind, source=self.source)
        result.annotations = deepcopy(self.annotations)
        result._items = []
        for item in self._items:
            if isinstance(item, Element):
                copied = item.clone()
                copied._parent = result
                result._items.append(copied)
            else:
                result._items.append(item)  # Values and source spans are immutable.
        result._syntax = self._syntax
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
    def __init__(self, root: Element | None = None, *, representation='tree'):
        if representation not in ('tree', 'schematic', 'asc', 'dchxml'):
            raise ValueError('document representation must be tree, schematic, asc or dchxml')
        self._representation = representation
        self.root = root if root is not None else Element("")
        if self.root.kind or self.root.parent is not None:
            raise ValueError("document root must be an unnamed detached element")
        self.metadata: dict[str, object] = {}
        self.complete = True
        self.diagnostics: list[str] = []
        self._source_text: str | None = None
        self._source_bytes: bytes | None = None
        self._source_encoding: str = "utf-8"
        from .references import References
        self.references = References(self)
        self._reference_validator = None

    @property
    def representation(self):
        """Current API view, independent of input provenance or export format."""
        return self._representation

    def select(self, path: str) -> list[Element]:
        return self.root.select(path)

    def one(self, path: str) -> Element:
        return self.root.one(path)

    def find_all(self, kind: str, *, where=None) -> list[Element]:
        return self.root.find_all(kind, recursive=True, where=where)

    def rebuild_index(self) -> dict[str, Element]:
        index = {}
        for node in self.root.walk(include_self=True):
            if node.uid in index:
                raise ValueError(f"duplicate element identity: {node.uid}")
            index[node.uid] = node
            for child in node.children():
                if child.parent is not node:
                    raise ValueError(f"inconsistent parent for {child.uid}")
        return index

    def get(self, uid: str) -> Element:
        try:
            return self.rebuild_index()[uid]
        except KeyError:
            raise LookupError(f"unknown element identity: {uid}") from None

    def rebuild(self, *, force=True):
        """Validate element identities and project stable references into indices."""
        index = self.rebuild_index()
        if self._reference_validator:
            self._reference_validator(self)
        self.references.synchronize(force=force)
        return index

    def unresolved(self) -> list[str]:
        return self.diagnostics + [f"{n.path}: {n.annotations['incomplete']}"
                                   for n in self.root.walk() if n.annotations.get("incomplete")]

    def clone(self) -> "Document":
        from copy import deepcopy
        doc = Document(self.root.clone(), representation=self.representation)
        doc.metadata = deepcopy(self.metadata)
        doc.complete, doc.diagnostics = self.complete, list(self.diagnostics)
        doc._source_text, doc._source_bytes = self._source_text, self._source_bytes
        doc._source_encoding = self._source_encoding
        mapping = dict(zip(self.root.walk(include_self=True), doc.root.walk(include_self=True)))
        doc.references = self.references.clone_to(doc, mapping)
        doc._reference_validator = self._reference_validator
        return doc

    @export_diagnostics('asc')
    def as_asc(self, *, context=None, report=None) -> "Document":
        """Create an owned ASC-format document from the current shared design."""
        from .asc_export import project_document
        return project_document(self,context=context,report=report)

    @import_diagnostics()
    def as_schematic(self, *, report=None) -> "Document":
        """Normalize public ASC or DCHXML into editable shared schematic data.

        Missing binary-only facts receive declared defaults. DCH input already
        has this representation and returns an independent clone.
        """
        if self.representation == 'schematic':
            return self.clone()
        if self.representation == 'dchxml':
            from .dchxml_import import import_schematic
            return import_schematic(self)
        from .asc_import import import_schematic
        return import_schematic(self)

    @export_diagnostics('asc')
    def to_asc(self, *, preserve=True, allow_partial=False, context=None, report=None) -> str:
        if self.representation == 'dchxml':
            raise ValueError('normalize XML with as_schematic() before ASC semantic projection')
        if context is not None or not allow_partial and self.representation == 'schematic':
            return self.as_asc(context=context,report=report).to_asc(preserve=preserve)
        if not allow_partial and (self.representation == 'schematic' or
                any(node.annotations.get('requires_asc_projection') for node in self.root.walk(include_self=True))):
            raise IncompleteDocumentError('shared schematic data requires an ASC export context')
        from .asc import dumps
        if not allow_partial:
            gaps = self.unresolved()
            if not self.complete or gaps:
                raise IncompleteDocumentError("document is incomplete: " + "; ".join(gaps))
            self.rebuild(force=False)
        return dumps(self, preserve=preserve)

    @export_diagnostics('asc')
    def to_asc_bytes(self, *, preserve=True, allow_partial=False, encoding: str | None = None, context=None, report=None) -> bytes:
        if context is not None or not allow_partial and self.representation == 'schematic':
            if encoding is not None:
                from dataclasses import replace
                from .asc_export import AscExportContext
                if context is not None and not isinstance(context, AscExportContext):
                    raise TypeError('ASC conversion requires an AscExportContext')
                context = replace(context, encoding=encoding) if context is not None else AscExportContext(encoding=encoding)
            return self.as_asc(context=context,report=report).to_asc_bytes(preserve=preserve,encoding=encoding)
        text = self.to_asc(preserve=preserve, allow_partial=allow_partial)
        if preserve and not self.root._dirty and self._source_bytes is not None and encoding is None:
            return self._source_bytes
        selected=encoding or self._source_encoding
        import codecs
        if codecs.lookup(selected).name=='cp1252':
            from .windows_1252 import encode
            return encode(text,best_fit=False)
        return text.encode(selected)

    @export_diagnostics('asc')
    def save_asc(self, path, **options):
        from pathlib import Path
        data = self.to_asc_bytes(**options)
        Path(path).write_bytes(data)

    @export_diagnostics('dch')
    def to_dch_bytes(self, *, version=46, context=None, report=None) -> bytes:
        """Serialize current data to the supported binary output schema."""
        from .dch_write import encode
        return encode(self,version=version,context=context,report=report)

    @export_diagnostics('dch')
    def save_dch(self,path,*,version=46,context=None,report=None):
        from pathlib import Path
        data=self.to_dch_bytes(version=version,context=context,report=report)
        Path(path).write_bytes(data)

    @export_diagnostics('dchxml')
    def as_dchxml(self, *, context=None, version=46, report=None) -> "Document":
        """Project shared schematic data to an independent public XML document."""
        from .dchxml_export import project_document
        return project_document(self, context=context, version=version, report=report)

    @export_diagnostics('dchxml')
    def to_dchxml(self, *, newline='\n', context=None, version=46, report=None) -> str:
        if context is not None or self.representation == 'schematic':
            return self.as_dchxml(context=context, version=version, report=report).to_dchxml(newline=newline)
        from .dchxml import dumps
        return dumps(self, newline=newline)

    @export_diagnostics('dchxml')
    def to_dchxml_bytes(self, *, newline='\n', context=None, version=46, report=None) -> bytes:
        return self.to_dchxml(newline=newline, context=context, version=version, report=report).encode('utf-8')

    @export_diagnostics('dchxml')
    def save_dchxml(self, path, *, newline='\n', context=None, version=46, report=None):
        from pathlib import Path
        data = self.to_dchxml_bytes(newline=newline, context=context, version=version, report=report)
        Path(path).write_bytes(data)
