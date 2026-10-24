"""Small explicit path selectors; no eval and no dependency on source offsets."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from functools import lru_cache
import re
from .model import (ELEMENT_NAME)


_STEP = re.compile(r"(" + ELEMENT_NAME + r"|\*)(?:\[(.*)\])?\Z", re.DOTALL)
_FILTER = re.compile(r"(@\d+|" + ELEMENT_NAME + r")\s*=\s*(.*)\Z", re.DOTALL)


def _scan_steps(path):
    i, length = 0, len(path)
    while i < length:
        recursive = path.startswith("//", i)
        if recursive:
            i += 2
        elif path[i] == "/":
            i += 1
        start, quote, brackets = i, None, 0
        while i < length:
            c = path[i]
            if quote:
                if c == quote:
                    if i+1 < length and path[i+1] == quote:
                        i += 1  # A doubled matching quote is literal text.
                    else:
                        quote = None
            elif c in "\"'":
                quote = c
            elif c == "[":
                brackets += 1
            elif c == "]":
                brackets -= 1
            elif c == "/" and not brackets:
                break
            i += 1
        token = path[start:i]
        if not token or quote or brackets:
            raise ValueError(f"invalid selector: {path!r}")
        match = _STEP.fullmatch(token)
        if not match:
            raise ValueError(f"unsupported selector step: {token!r}")
        yield recursive, match[1], match[2]


@lru_cache(maxsize=1024)
def _steps(path):
    # Cache syntax only. Matches always come from the current tree.
    return tuple(_scan_steps(path))


def _predicate(nodes, text):
    if text is None:
        return nodes
    if text.isdigit():
        ordinal = int(text)
        if ordinal < 1:
            raise ValueError("selector ordinals are one-based")
        return nodes[ordinal-1:ordinal]
    match = _FILTER.fullmatch(text)
    if not match:
        raise ValueError(f"unsupported predicate: {text!r}")
    key, literal = match.groups()
    literal = literal.strip()
    if len(literal) >= 2 and literal[0] in "\"'" and literal[-1] == literal[0]:
        want = literal[1:-1].replace(literal[0]*2, literal[0])
    elif literal.lower() in ('true', 'false'):
        want = literal.lower() == 'true'
    else:
        try:
            want = Decimal(literal)
        except InvalidOperation:
            raise ValueError(f"predicate value must be quoted text, a boolean or a number: {literal!r}") from None
        if not want.is_finite():
            raise ValueError('predicate numbers must be finite')
    out = []
    for node in nodes:
        if key.startswith("@"):
            index = int(key[1:])
            actual = node.values[index] if index < len(node.values) else None
        else:
            actual = node.scalar(key)
        if isinstance(actual, bool) == isinstance(want, bool) and actual == want:
            out.append(node)
    return out


def select(root, path):
    if not path:
        raise ValueError("selector cannot be empty")
    if path.startswith("/"):
        while root.parent is not None:
            root = root.parent
    if path == "/":
        return [root]
    current = [root]
    for recursive, kind, predicate in _steps(path):
        next_nodes, seen = [], set()
        for parent in current:
            candidates = parent.descendants(None if kind == "*" else kind) if recursive else parent.children(None if kind == "*" else kind)
            for node in _predicate(candidates, predicate):
                if node.uid not in seen:
                    next_nodes.append(node)
                    seen.add(node.uid)
        current = next_nodes
    return current
