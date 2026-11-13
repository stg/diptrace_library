"""ASC lexical syntax shared by the document-family adapters.

This module handles parentheses, scalar values and optional source spelling.
Family normalization, schemas, references and output layout belong to adapters.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
import re

from .model import Document, Element, SourceSpan, Value
from .numbers import fixed_number_text


_TOKEN = re.compile(r'\s+|[()]|"[^"]*"|[^\s()"]+', re.DOTALL)
_NUMBER = re.compile(r"-?(?:[0-9]+(?:\.[0-9]+)?)(%)?\Z")
_NAME = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z")
_ATOM = re.compile(r'[^\s()"]+\Z')


@dataclass(frozen=True, slots=True)
class _Syntax:
    text: str
    start: int
    end: int
    head_end: int
    spans: tuple[tuple[int, int], ...]
    tail_start: int
    column: int


@lru_cache(maxsize=4096)
def _plain_value(token):
    """Share immutable token values when source positions are not requested."""
    if token.startswith('"'):
        return Value(token[1:-1], 'string', lexeme=token)
    if _NUMBER.fullmatch(token):
        unit = '%' if token.endswith('%') else ''
        number = token.rstrip('%')
        return Value(Decimal(number) if '.' in number else int(number), 'number', unit, token)
    return Value(token, 'symbol', lexeme=token)


def loads(text: str, *, source: str | None = None, document_factory=Document, retain_source=True) -> Document:
    doc = document_factory(representation='asc')
    stack = [doc.root]
    frames = [[0, 0, []]] if retain_source else None
    expecting_name = False
    cursor = 0
    for match in _TOKEN.finditer(text):
        if match.start() != cursor:
            raise ValueError(f"invalid ASC token at character {cursor}")
        cursor = match.end()
        token = match.group()
        if token.isspace():
            continue
        if expecting_name:
            if not _NAME.fullmatch(token):
                raise ValueError(f"expected element name at character {match.start()}")
            stack[-1]._kind = token
            if retain_source:
                frames[-1][1] = match.end()
            expecting_name = False
        elif token == "(":
            node = Element("")
            node._parent = stack[-1]
            stack[-1]._items.append(node)
            stack.append(node)
            if retain_source:
                frames.append([match.start(), match.end(), []])
            expecting_name = True
        elif token == ")":
            if len(stack) == 1:
                raise ValueError(f"unexpected ')' at character {match.start()}")
            node = stack.pop()
            if retain_source:
                start, head_end, spans = frames.pop()
                node.source = SourceSpan("asc", start, match.end(), source)
                node._syntax = _Syntax(text, start, match.end(), head_end, tuple(spans), match.start(),
                                       start - text.rfind("\n", 0, start) - 1)
            node._dirty = node._reordered = False
            if retain_source:
                frames[-1][2].append((start, match.end()))
        else:
            if len(stack) == 1:
                raise ValueError(f"value outside an ASC element at character {match.start()}")
            span = SourceSpan("asc", match.start(), match.end(), source) if retain_source else None
            if not retain_source:
                value = _plain_value(token)
            elif token.startswith('"'):
                value = Value(token[1:-1], "string", lexeme=token, source=span)
            elif _NUMBER.fullmatch(token):
                unit = "%" if token.endswith("%") else ""
                number = token.rstrip("%")
                value = Value(Decimal(number) if "." in number else int(number), "number", unit, token, span)
            else:
                # Some public records use unquoted names, including layer
                # names containing punctuation. Only record heads are names in
                # the identifier grammar; scalar atoms have a wider grammar.
                value = Value(token, "symbol", lexeme=token, source=span)
            stack[-1]._items.append(value)
            if retain_source:
                frames[-1][2].append((match.start(), match.end()))
    if cursor != len(text):
        raise ValueError(f"unterminated string at character {cursor}")
    if expecting_name or len(stack) != 1:
        raise ValueError("unclosed ASC element")
    if retain_source:
        spans = frames[0][2]
        doc.root._syntax = _Syntax(text, 0, len(text), 0, tuple(spans), len(text), 0)
    doc.root._dirty = doc.root._reordered = False
    doc._source_text = text if retain_source else None
    doc.metadata.update(source_format="asc", source_path=source)
    return doc


def loads_bytes(data, *, source=None, encoding=None, document_factory=Document, retain_source=True) -> Document:
    """Decode an ASC byte buffer using the same policy as file input."""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError('ASC input must be bytes, bytearray or memoryview')
    data = bytes(data)
    if encoding is None:
        encoding = "utf-8-sig" if data.startswith(b"\xef\xbb\xbf") else "cp1252"
    import codecs
    if codecs.lookup(encoding).name == 'cp1252':
        from .text.windows_1252 import decode
        text = decode(data)
    else:
        text = data.decode(encoding)
    doc = loads(text, source=source, document_factory=document_factory, retain_source=retain_source)
    doc._source_bytes, doc._source_encoding = data if retain_source else None, encoding
    return doc


def read(path: str | Path, *, encoding: str | None = None, document_factory=Document) -> Document:
    path = Path(path)
    return loads_bytes(path.read_bytes(), source=str(path), encoding=encoding, document_factory=document_factory)


def _value(value: Value, preserve: bool):
    if preserve and value.lexeme is not None:
        return value.lexeme
    if value.kind == "number":
        return fixed_number_text(value.value) + value.unit
    if value.kind == "symbol":
        text = str(value.value)
        if not _ATOM.fullmatch(text):
            raise ValueError(f'invalid ASC symbol: {text!r}')
        return text
    if value.kind == "boolean":
        return '"Y"' if value.value else '"N"'
    text = str(value.value)
    if '"' in text:
        raise ValueError("embedded double quotes have no verified ASC escaping rule")
    return '"' + text + '"'


def _shift_indent(raw: str, delta: int) -> str:
    """Move layout without altering line breaks/spaces inside quoted values."""
    if not delta or "\n" not in raw:
        return raw
    quoted = False
    lines = raw.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if i and not quoted:
            if delta > 0:
                line = " " * delta + line
            else:
                amount = min(-delta, len(line) - len(line.lstrip(" ")))
                line = line[amount:]
        if line.count('"') % 2:
            quoted = not quoted
        lines[i] = line
    return "".join(lines)


def _render(node: Element, indent: int, preserve: bool) -> str:
    if node.kind and not _NAME.fullmatch(node.kind):
        raise ValueError(f'element name is not an ASC identifier: {node.kind!r}')
    syntax = node._syntax
    if preserve and syntax is not None and not node._dirty:
        raw = syntax.text[syntax.start:syntax.end]
        return _shift_indent(raw, indent-syntax.column) if node.kind else raw
    if preserve and syntax is not None and not node._reordered:
        # Scalar edits retain all surrounding whitespace and original spelling.
        out = ["(" + node.kind if node.kind else ""]
        cursor = syntax.head_end
        for item, (start, end) in zip(node._items, syntax.spans):
            out.append(syntax.text[cursor:start])
            item_indent = start - syntax.text.rfind("\n", 0, start) - 1
            out.append(_render(item, item_indent, preserve) if isinstance(item, Element) else _value(item, preserve))
            cursor = end
        out.append(syntax.text[cursor:syntax.end])
        raw = "".join(out)
        return _shift_indent(raw, indent-syntax.column) if node.kind else raw
    if not node.kind:
        return "\n".join(_render(n, 0, preserve) for n in node.children()) + ("\n" if node.children() else "")
    out = ["(" + node.kind]
    multiline = False
    for item in node._items:
        if isinstance(item, Element):
            multiline = True
            out.extend(("\n", " " * (indent+2), _render(item, indent+2, preserve)))
        else:
            out.extend(("\n" + " " * (indent+2) if multiline else " ", _value(item, preserve)))
    if multiline:
        out.extend(("\n", " " * indent))
    out.append(")")
    return "".join(out)


def dumps(document: Document, *, preserve=True) -> str:
    return _render(document.root, 0, preserve)
