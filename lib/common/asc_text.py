"""Text restrictions shared by ASC document-family writers."""
import codecs

from .conversion import info, warn
from .model import Value
from .text.windows_1252 import project as ansi_text

_TOKEN_ESCAPES = str.maketrans({char: '!' for char in '() "\r\n'})


def quoted_text(value):
    return '"' + value.replace('"', '!').replace('\r', '!').replace('\n', '!') + '"'


def raw_token(value):
    """Read a text position whose quotes and numeric spelling are literal."""
    return value.lexeme if value.lexeme is not None else str(value.value)


def project_text(document, *, encoding='cp1252', report=None,
                 receiver_normalizes=None, redundant_text=None, unquoted_text=None):
    """Adapt strings on an owned output view; report irreversible substitutions.

    Document families identify unquoted text positions, receiver-specific rules
    and redundant text views. Their policies stay outside this shared engine.
    """
    encoding = codecs.lookup(encoding).name
    sanitized, tokens, encoded, compatibility, receiver_text = [], [], [], [], []
    for node in document.root.walk():
        redundant = redundant_text(node) if redundant_text is not None else False
        sanitize_changed = token_changed = encode_changed = receiver_changed = False
        for index, value in enumerate(node.arguments):
            token = unquoted_text is not None and unquoted_text(node, index)
            if value.kind != 'string' and not token:
                continue
            receiver_changed |= ('!' in value.value and receiver_normalizes is not None
                                 and receiver_normalizes(node, index))
            if token:
                text = value.value.translate(_TOKEN_ESCAPES)
                token_changed |= text != value.value
            else:
                text = quoted_text(value.value)[1:-1]
                sanitize_changed |= text != value.value
            projected = ansi_text(text) if encoding == 'cp1252' else text.encode(encoding).decode(encoding)
            encode_changed |= projected != text
            kind = 'symbol' if token else value.kind
            if projected != value.value or kind != value.kind:
                node.set_argument(index, Value(projected, kind, value.unit, source=value.source))
        if redundant and (sanitize_changed or token_changed or encode_changed):
            compatibility.append(node)
        elif sanitize_changed:
            sanitized.append(node)
        if token_changed and not redundant:
            tokens.append(node)
        if encode_changed and not redundant:
            encoded.append(node)
        if receiver_changed and not redundant:
            receiver_text.append(node)
    if compatibility:
        info(report, 'asc-cell-text-compatibility', 'asc', 'the redundant legacy cell text representation is normalized', compatibility,
             recoverability='TextLine supplies the current cell text; restrictions of those line values are reported separately')
    if sanitized:
        warn(report, 'asc-text-sanitization', 'asc', 'quotes and line breaks in ASC strings become exclamation marks', sanitized,
             recoverability='original characters cannot be recovered from ASC; authoring text remains intact')
    if tokens:
        warn(report, 'asc-token-sanitization', 'asc',
             'parentheses, spaces, quotes and line breaks in unquoted ASC text become exclamation marks', tokens,
             recoverability='the receiving application reads these marks as spaces; authoring text remains intact')
    if encoded:
        warn(report, 'asc-text-encoding', 'asc', f'ASC strings use {encoding} character substitutions', encoded,
             recoverability='original characters cannot be recovered from ASC; authoring Unicode remains intact')
    if receiver_text:
        warn(report, 'asc-reader-text-normalization', 'asc',
             'the receiving application replaces literal ! with spaces in these text fields', receiver_text,
             recoverability='literal ! remains in the ASC file and this library preserves it; binary/XML formats avoid this receiver conversion')
