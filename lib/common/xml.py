"""Typed XML syntax shared by DipTrace document-family adapters.

Each family supplies its public vocabulary as a dialect. Element ownership,
XML character validation and parsing are independent of family normalization.
"""
from decimal import Decimal
import math
from pathlib import Path
import re
from xml.parsers import expat
from xml.sax.saxutils import escape

from dataclasses import dataclass, field
from .model import Document, Element, Value, _valid_element_name

_NUMBER = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z')

@dataclass(frozen=True)
class XmlDialect:
    """Public XML vocabulary; ambiguous names can use (owner, name) keys."""
    format: str = 'xml'
    source_type: str | None = None
    representation: str = 'xml'
    number_attributes: frozenset[str | tuple[str, str]] = field(default_factory=frozenset)
    boolean_attributes: frozenset[str | tuple[str, str]] = field(default_factory=frozenset)
    boolean_text: frozenset[str | tuple[str, str]] = field(default_factory=frozenset)
    number_text: frozenset[tuple[str, str]] = field(default_factory=frozenset)


DEFAULT_DIALECT = XmlDialect()


def _number(text):
    if not _NUMBER.fullmatch(text.strip()):
        raise ValueError(f'invalid XML numeric value: {text!r}')
    value = Decimal(text.strip())
    return Value(int(value) if '.' not in text and 'e' not in text.lower() else value,
                 'number', lexeme=text)


def _boolean(text):
    if text not in ('Y', 'N'):
        raise ValueError(f'invalid XML boolean value: {text!r}')
    return Value(text == 'Y', 'boolean')


def _listed(vocabulary, parent, name):
    return name in vocabulary or (parent, name) in vocabulary


def set_attribute(node, name, value):
    """Add or edit an XML attribute through the ordinary model field API."""
    if not _valid_element_name(name):
        raise ValueError(f'invalid XML attribute name: {name!r}')
    matches = [child for child in node.children(name)
               if child.annotations.get('xml_role') == 'attribute']
    if len(matches) > 1:
        raise ValueError(f'{node.path}: duplicate XML attribute {name}')
    field = matches[0] if matches else node.add(name)
    field.set_values(value)
    field.annotations['xml_role'] = 'attribute'
    return field


def _attribute_value(name, text, dialect, parent=''):
    if _listed(dialect.boolean_attributes, parent, name):
        return _boolean(text)
    if _listed(dialect.number_attributes, parent, name):
        return _number(text)
    return Value(text, 'string')


def loads(data, *, source=None, dialect=DEFAULT_DIALECT, document_factory=Document):
    """Read XML directly into Elements; unknown fields retain literal strings."""
    document = document_factory(representation=dialect.representation)
    parser = expat.ParserCreate()
    parser.ordered_attributes = True
    stack = [document.root]
    pending = [[]]

    def flush():
        if pending[-1]:
            stack[-1]._items.append(Value(''.join(pending[-1]), 'string'))
            pending[-1].clear()

    def start(name, attributes):
        if len(stack) > 256:
            raise ValueError('XML nesting exceeds 256 elements')
        if not _valid_element_name(name):
            raise ValueError(f'unsupported XML element name: {name!r}')
        flush()
        node = stack[-1].add(name)
        node.annotations.update(xml_role='element', xml_line=parser.CurrentLineNumber)
        for index in range(0, len(attributes), 2):
            key, text = attributes[index:index+2]
            set_attribute(node, key, _attribute_value(key, text, dialect, name))
        stack.append(node)
        pending.append([])

    def finish(name):
        flush()
        node = stack.pop()
        pending.pop()
        children = [child for child in node.children()
                    if child.annotations.get('xml_role') != 'attribute']
        values = node.arguments
        if children and not any(str(value.value).strip() for value in values):
            node._items = [item for item in node._items if isinstance(item, Element)]
        elif not children and len(values) == 1:
            text = values[0].value
            parent = stack[-1].kind
            if _listed(dialect.boolean_text, parent, node.kind):
                node.set_values(_boolean(text))
            elif (parent, node.kind) in dialect.number_text:
                node.set_values(_number(text))

    def comment(text):
        flush()
        node = stack[-1].add('Comment', text)
        node.annotations['xml_role'] = 'comment'

    def instruction(target, text):
        flush()
        node = stack[-1].add('ProcessingInstruction', target, text)
        node.annotations['xml_role'] = 'instruction'

    def doctype(*arguments):
        raise ValueError('DipTrace XML does not use document type declarations')

    parser.StartElementHandler = start
    parser.EndElementHandler = finish
    parser.CharacterDataHandler = lambda text: pending[-1].append(text)
    parser.CommentHandler = comment
    parser.ProcessingInstructionHandler = instruction
    parser.StartDoctypeDeclHandler = doctype
    try:
        parser.Parse(data, True)
    except expat.ExpatError as error:
        raise ValueError(f'invalid {dialect.format.upper()} at line {error.lineno}, column {error.offset}: {error}') from error
    root = document.root.child('Source')
    if root is None or dialect.source_type is not None and root.scalar('Type') != dialect.source_type:
        raise ValueError(f'expected Source Type="{dialect.source_type}"' if dialect.source_type else 'expected Source element')
    for node in document.root.walk(include_self=True):
        node._dirty = node._reordered = False
    document.metadata.update(source_format=dialect.format, source_path=source,
                             source_version=root.scalar('Version'),
                             units=root.scalar('Units'),
                             xml_semantic_mapping_complete=False)
    return document


def read(path, *, dialect=DEFAULT_DIALECT, document_factory=Document):
    path = Path(path)
    return loads(path.read_bytes(), source=str(path), dialect=dialect, document_factory=document_factory)


def _text(value):
    if value.unit:
        raise ValueError('XML scalar values cannot have an implicit unit suffix')
    if value.kind == 'boolean':
        text = 'Y' if value.value else 'N'
    elif value.kind == 'number':
        if not math.isfinite(float(value.value)):
            raise ValueError('XML numbers must be finite')
        text = str(value.value) if isinstance(value.value, int) else format(value.value, 'f')
    else:
        text = str(value.value)
    if any(ord(char) < 32 and char not in '\t\n\r' or
           0xd800 <= ord(char) <= 0xdfff or ord(char) in (0xfffe, 0xffff)
           for char in text):
        raise ValueError('value contains a character outside XML 1.0')
    return text


def _render(node, newline, dialect):
    role = node.annotations.get('xml_role')
    if role in ('comment', 'instruction'):
        count = 1 if role == 'comment' else 2
        if (node.children() or len(node.arguments) != count
                or any(value.kind != 'string' for value in node.arguments)):
            raise ValueError(f'{node.path}: XML {role} requires {count} string values and no children')
        values = tuple(_text(value) for value in node.arguments)
    if role == 'comment':
        text, = values
        if '--' in text or text.endswith('-'):
            raise ValueError('invalid XML comment')
        return '<!--'+text+'-->'
    if role == 'instruction':
        target, text = values
        if not _valid_element_name(target) or '?>' in text or target.lower() == 'xml':
            raise ValueError('invalid XML processing instruction')
        return '<?'+target+(' '+text if text else '')+'?>'
    if not _valid_element_name(node.kind):
        raise ValueError(f'invalid XML element name: {node.kind!r}')
    if not node.children() and len(node.arguments) == 1:
        parent = node.parent.kind if node.parent is not None else ''
        expected = ('boolean' if _listed(dialect.boolean_text, parent, node.kind) else
                    'number' if (parent, node.kind) in dialect.number_text else None)
        if expected is not None and node.arguments[0].kind != expected:
            raise ValueError(f'{node.path}: expected an XML {expected} value')
    attributes, content = [], []
    seen = set()
    for item in node._items:
        if isinstance(item, Element) and item.annotations.get('xml_role') == 'attribute':
            if item.kind in seen or not _valid_element_name(item.kind):
                raise ValueError(f'{node.path}: duplicate or invalid XML attribute {item.kind!r}')
            if len(item.arguments) != 1 or item.children():
                raise ValueError(f'{item.path}: an XML attribute needs one scalar value')
            expected = ('boolean' if _listed(dialect.boolean_attributes, node.kind, item.kind) else
                        'number' if _listed(dialect.number_attributes, node.kind, item.kind) else None)
            if expected is not None and item.arguments[0].kind != expected:
                raise ValueError(f'{item.path}: expected an XML {expected} value')
            seen.add(item.kind)
            value = escape(_text(item.arguments[0]), {'"': '&quot;', '\t': '&#9;', '\n': '&#10;', '\r': '&#13;'})
            attributes.append(' '+item.kind+'="'+value+'"')
        else:
            content.append(item)
    opening = '<'+node.kind+''.join(attributes)
    if not content:
        return opening+'/>'
    if all(isinstance(item, Element) for item in content):
        body = newline+newline.join(_render(item, newline, dialect) for item in content)+newline
    else:
        body = ''.join(_render(item, newline, dialect) if isinstance(item, Element)
                       else escape(_text(item), {'\r': '&#13;'}) for item in content)
    return opening+'>'+body+'</'+node.kind+'>'


def dumps(document, *, newline='\n', dialect=DEFAULT_DIALECT):
    """Reconstruct XML from current typed data; no source-text replay."""
    if newline not in ('\n', '\r\n'):
        raise ValueError('XML newline must be LF or CRLF')
    root = document.root.child('Source')
    if root is None or dialect.source_type is not None and root.scalar('Type') != dialect.source_type:
        raise ValueError(f'{dialect.format.upper()} output requires a Source element'
                         + (f' with Type="{dialect.source_type}"' if dialect.source_type else ''))
    elements = [node for node in document.root.children()
                if node.annotations.get('xml_role') not in ('comment', 'instruction')]
    if elements != [root] or any(str(value.value).strip() for value in document.root.arguments):
        raise ValueError('XML output requires one Source element and no text outside it')
    document.rebuild(force=False)
    return '<?xml version="1.0" encoding="utf-8"?>'+newline+newline.join(
        _render(node, newline, dialect) for node in document.root.children())+newline
