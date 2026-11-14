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
from .xml_plan import XmlBuilder, XmlPlan
from .numbers import fixed_number_text

_NUMBER = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z')
_FORBIDDEN_TEXT = re.compile('[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]')

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
    root_tag: str = 'Source'


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


def syntax_role(node):
    """Inspect an XML role without creating an otherwise absent notes map."""
    notes = node._annotations
    return notes.get('xml_role') if notes is not None else None


def set_attribute(node, name, value):
    """Add or edit an XML attribute through the ordinary model field API."""
    if not _valid_element_name(name):
        raise ValueError(f'invalid XML attribute name: {name!r}')
    if type(node) is XmlBuilder:
        return node.attribute(name, value)
    matches = [child for child in node.children(name)
               if syntax_role(child) == 'attribute']
    if len(matches) > 1:
        raise ValueError(f'{node.path}: duplicate XML attribute {name}')
    if matches:
        field = matches[0]
        field.set_values(value)
        field.annotations['xml_role'] = 'attribute'
        return field
    field = Element(name, value)
    field.annotations['xml_role'] = 'attribute'
    return node.append(field)


def _attribute_value(name, text, dialect, parent=''):
    if _listed(dialect.boolean_attributes, parent, name):
        return _boolean(text)
    if _listed(dialect.number_attributes, parent, name):
        return _number(text)
    return Value(text, 'string')


def loads(data, *, source=None, dialect=DEFAULT_DIALECT, document_factory=Document, retain_source=True):
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
        node = stack[-1]._append_import(Element(name))
        node.annotations['xml_role'] = 'element'
        if retain_source:
            node.annotations['xml_line'] = parser.CurrentLineNumber
        for index in range(0, len(attributes), 2):
            key, text = attributes[index:index+2]
            attribute = Element(key, _attribute_value(key, text, dialect, name))
            attribute.annotations['xml_role'] = 'attribute'
            node._append_import(attribute)
        stack.append(node)
        pending.append([])

    def finish(name):
        flush()
        node = stack.pop()
        pending.pop()
        children = [child for child in node.children()
                    if syntax_role(child) != 'attribute']
        values = node.arguments
        if children and not any(str(value.value).strip() for value in values):
            node._items = [item for item in node._items if isinstance(item, Element)]
        elif not children and len(values) == 1:
            text = values[0].value
            parent = stack[-1].kind
            if _listed(dialect.boolean_text, parent, node.kind):
                node._items = [_boolean(text), *node.children()]
            elif (parent, node.kind) in dialect.number_text:
                node._items = [_number(text), *node.children()]

    def comment(text):
        flush()
        node = stack[-1]._append_import(Element('Comment', text))
        node.annotations['xml_role'] = 'comment'

    def instruction(target, text):
        flush()
        node = stack[-1]._append_import(Element('ProcessingInstruction', target, text))
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
    root = document.root.child(dialect.root_tag)
    if root is None or dialect.source_type is not None and root.scalar('Type') != dialect.source_type:
        raise ValueError(f'expected {dialect.root_tag} Type="{dialect.source_type}"'
                         if dialect.source_type else f'expected {dialect.root_tag} element')
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


def _text(value, canonical_numbers=False):
    if value.unit:
        raise ValueError('XML scalar values cannot have an implicit unit suffix')
    if value.kind == 'boolean':
        text = 'Y' if value.value else 'N'
    elif value.kind == 'number':
        if not math.isfinite(float(value.value)):
            raise ValueError('XML numbers must be finite')
        text = fixed_number_text(value.value)
        # Equivalent numbers have one output spelling, independent of retained
        # source precision or calculation history. No decimal arithmetic rounds
        # the value, including under a caller's unusually small context.
        if canonical_numbers:
            if '.' in text:
                text = text.rstrip('0').rstrip('.')
            if text == '-0':
                text = '0'
    else:
        text = str(value.value)
    if _FORBIDDEN_TEXT.search(text):
        raise ValueError('value contains a character outside XML 1.0')
    return text


def _render(node, newline, dialect, canonical_numbers=False):
    role = syntax_role(node)
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
        if isinstance(item, Element) and syntax_role(item) == 'attribute':
            if item.kind in seen or not _valid_element_name(item.kind):
                raise ValueError(f'{node.path}: duplicate or invalid XML attribute {item.kind!r}')
            if len(item.arguments) != 1 or item.children():
                raise ValueError(f'{item.path}: an XML attribute needs one scalar value')
            expected = ('boolean' if _listed(dialect.boolean_attributes, node.kind, item.kind) else
                        'number' if _listed(dialect.number_attributes, node.kind, item.kind) else None)
            if expected is not None and item.arguments[0].kind != expected:
                raise ValueError(f'{item.path}: expected an XML {expected} value')
            seen.add(item.kind)
            value = escape(_text(item.arguments[0], canonical_numbers), {'"': '&quot;', '\t': '&#9;', '\n': '&#10;', '\r': '&#13;'})
            attributes.append(' '+item.kind+'="'+value+'"')
        else:
            content.append(item)
    opening = '<'+node.kind+''.join(attributes)
    if not content:
        return opening+'/>'
    if all(isinstance(item, Element) for item in content):
        body = newline+newline.join(_render(item, newline, dialect, canonical_numbers) for item in content)+newline
    else:
        body = ''.join(_render(item, newline, dialect, canonical_numbers) if isinstance(item, Element)
                       else escape(_text(item, canonical_numbers), {'\r': '&#13;'}) for item in content)
    return opening+'>'+body+'</'+node.kind+'>'


def dumps(document, *, newline='\n', dialect=DEFAULT_DIALECT, canonical_numbers=False):
    """Reconstruct XML from current typed data; no source-text replay."""
    if newline not in ('\n', '\r\n'):
        raise ValueError('XML newline must be LF or CRLF')
    root = document.root.child(dialect.root_tag)
    if root is None or dialect.source_type is not None and root.scalar('Type') != dialect.source_type:
        raise ValueError(f'{dialect.format.upper()} output requires a {dialect.root_tag} element'
                         + (f' with Type="{dialect.source_type}"' if dialect.source_type else ''))
    elements = [node for node in document.root.children()
                if syntax_role(node) not in ('comment', 'instruction')]
    if elements != [root] or any(str(value.value).strip() for value in document.root.arguments):
        raise ValueError(f'XML output requires one {dialect.root_tag} element and no text outside it')
    document._synchronize(force=False)
    return '<?xml version="1.0" encoding="utf-8"?>'+newline+newline.join(
        _render(node, newline, dialect, canonical_numbers) for node in document.root.children())+newline


def render_plan(plan, *, newline='\n', dialect=DEFAULT_DIALECT, canonical_numbers=False):
    """Serialize generated XML facts without allocating an editable tree.

    Plans have no ownership or edit graph: their producer owns destination
    mapping and reference checks. This boundary checks XML names, vocabulary
    types, duplicate attributes, characters and units on every call. It also
    accepts fragments, so a document writer can compose already checked plans.
    """
    if newline not in ('\n', '\r\n'):
        raise ValueError('XML newline must be LF or CRLF')

    def render(node, parent, depth):
        if not isinstance(node, XmlPlan):
            raise TypeError('XML plan children must be XmlPlan records')
        if depth > 256:
            raise ValueError('XML nesting exceeds 256 elements')
        if not node.kind or not _valid_element_name(node.kind):
            raise ValueError(f'invalid XML element name: {node.kind!r}')
        if any(not isinstance(value, Value) for value in node.arguments):
            raise TypeError('XML plan text requires typed scalar values')
        if not node.children and not node.attributes and len(node.arguments) == 1:
            expected = ('boolean' if _listed(dialect.boolean_text, parent, node.kind) else
                        'number' if (parent, node.kind) in dialect.number_text else None)
            if expected is not None and node.arguments[0].kind != expected:
                raise ValueError(f'{node.kind}: expected an XML {expected} value')
        attributes, seen = [], set()
        for name, value in node.attributes:
            if name in seen or not name or not _valid_element_name(name):
                raise ValueError(f'{node.kind}: duplicate or invalid XML attribute {name!r}')
            if not isinstance(value, Value):
                raise TypeError('XML plan attributes require typed scalar values')
            expected = ('boolean' if _listed(dialect.boolean_attributes, node.kind, name) else
                        'number' if _listed(dialect.number_attributes, node.kind, name) else None)
            if expected is not None and value.kind != expected:
                raise ValueError(f'{node.kind}/{name}: expected an XML {expected} value')
            seen.add(name)
            text = escape(_text(value, canonical_numbers), {'"': '&quot;', '\t': '&#9;', '\n': '&#10;', '\r': '&#13;'})
            attributes.append(' '+name+'="'+text+'"')
        opening = '<'+node.kind+''.join(attributes)
        if not node.arguments and not node.children:
            return opening+'/>'
        if node.arguments:
            text = []
            for value in node.arguments:
                text.append(escape(_text(value, canonical_numbers), {'\r': '&#13;'}))
            body = ''.join(text)+''.join(render(child, node.kind, depth+1) for child in node.children)
        else:
            body = newline+newline.join(render(child, node.kind, depth+1) for child in node.children)+newline
        return opening+'>'+body+'</'+node.kind+'>'

    return render(plan, '', 1)


def dumps_plan(source, *, newline='\n', dialect=DEFAULT_DIALECT, canonical_numbers=False):
    """Emit a complete generated document from its declared root plan."""
    if (not isinstance(source, XmlPlan) or source.kind != dialect.root_tag
            or dialect.source_type is not None
            and getattr(dict(source.attributes).get('Type'), 'value', None) != dialect.source_type):
        raise ValueError(f'{dialect.format.upper()} output requires a {dialect.root_tag} element'
                         + (f' with Type="{dialect.source_type}"' if dialect.source_type else ''))
    return '<?xml version="1.0" encoding="utf-8"?>'+newline+render_plan(
        source, newline=newline, dialect=dialect, canonical_numbers=canonical_numbers)+newline
