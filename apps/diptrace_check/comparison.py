"""Compare named model facts without depending on a particular document family."""
from collections import Counter
from dataclasses import fields, is_dataclass
from decimal import Decimal
import hashlib

from lib import Element, ReferenceError
from lib.common.schema import MISSING


def value_identity(value):
    """Keep content and reference targets comparable across separate imports."""
    if isinstance(value, Element):
        return value.path
    if isinstance(value, bytes):
        return ('bytes', len(value), hashlib.sha256(value).hexdigest())
    if isinstance(value, (tuple, list)):
        return tuple(value_identity(v) for v in value)
    if is_dataclass(value):
        return (type(value).__name__, tuple((f.name, value_identity(getattr(value, f.name)))
                                           for f in fields(value)))
    if isinstance(value, dict):
        return tuple(sorted((k, value_identity(v)) for k, v in value.items()))
    return value


def _field_facts(path, definition, value):
    if definition.members and value is not None:
        for member, item in zip(definition.members, value):
            yield from _field_facts(path+'.'+member.name, member, item)
    elif definition.item_kind and value is not None:
        for i, item in enumerate(value):
            yield path+f'[{i}]', (definition.item_kind, definition.unit, value_identity(item))
    else:
        yield path, (definition.kind, definition.unit, value_identity(value))


def snapshot(document):
    """Record typed fields and links; exclude syntax and diagnostic metadata.

    Reading schema defaults avoids treating a newly materialized default as a
    data change. Actual links are checked in addition to their numeric selectors.
    """
    result = {}
    for node in document.root.walk(include_self=True):
        if node.schema is None:
            continue
        for name, definition in node.schema.fields.items():
            if definition.getter is None and node.child(name) is None and definition.default is MISSING:
                continue
            try:
                value = node.get(name, None if definition.default is MISSING else definition.default)
            except ReferenceError:
                value = ('unresolved',)
            result.update(_field_facts(node.path.rstrip('/')+'/'+name, definition, value))
    links = {}
    for reference in document.references:
        for index in reference.indices or (None,):
            owner = index.field.path if index is not None else reference.source.path
            argument = index.argument if index is not None else ''
            key = owner+f'/@reference[{reference.role},{argument}]'
            links.setdefault(key, []).append(reference.target.path)
    result.update((key, ('reference', '', tuple(sorted(values)))) for key, values in links.items())
    return result


def compare(before, after, *, tolerance, examples=20):
    """Small scalar numerical differences are reported, never silently removed.

    Integer settings, flags, text and references remain exact. The threshold is
    in each field's documented model unit, not an inferred physical distance.
    """
    counts, important, rounding, maxima = Counter(), [], [], {}
    for path in sorted(before.keys() | after.keys()):
        a, b = before.get(path), after.get(path)
        if a == b:
            continue
        delta = None
        if path not in before:
            kind = 'added'
        elif path not in after:
            kind = 'removed'
        elif (a[:2] == b[:2] and a[0] == 'number' and
              all(isinstance(v, (int, float, Decimal)) and not isinstance(v, bool) for v in (a[2], b[2]))):
            delta = abs(Decimal(str(a[2]))-Decimal(str(b[2])))
            if not delta.is_finite():
                raise ValueError('non-finite numeric comparison at '+path)
            unit = a[1] or 'unspecified model units'
            maxima[unit] = max(maxima.get(unit, Decimal(0)), delta)
            kind = 'rounding' if delta <= tolerance else 'numeric'
        else:
            kind = 'data'
        counts[kind] += 1
        sample = rounding if kind == 'rounding' else important
        if len(sample) < examples:
            sample.append(dict(path=path, kind=kind, unit=(b or a)[1],
                               before=a[2] if a else None, after=b[2] if b else None, delta=delta))
    return dict(counts=dict(counts), maximum_numeric_delta_by_unit=maxima,
                needs_review=any(n for kind, n in counts.items() if kind != 'rounding'),
                examples=(important+rounding)[:examples])
