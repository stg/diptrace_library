"""Allocate public keys on an export view around current and unresolved keys."""


def _key(value):
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError('public keys must be nonnegative integers') from None
    if isinstance(value,bool) or result != value or result < 0:
        raise ValueError('public keys must be nonnegative integers')
    return result


def allocate_keys(records, *, reserved=(), declared='Id', start=1):
    """Keep declared keys, then assign free keys in current order.

    The result maps record identities to keys. No field is added to the source;
    all declared keys are reserved before any missing key is generated.
    """
    records = tuple(records)
    start = _key(start)
    unavailable = {_key(value) for value in reserved}
    used, result = set(unavailable), {}
    for record in records:
        field = record.child(declared) if declared is not None else None
        if field is not None:
            if len(field.arguments) != 1 or field.arguments[0].kind != 'number' or field.arguments[0].unit:
                raise ValueError(f'{field.path}: public key requires one nonnegative integer')
            key = _key(field.values[0])
            if key in used:
                raise ValueError('public key duplicates another key or an unresolved assignment')
            result[record] = key
            used.add(key)
    for ordinal, record in enumerate(records,start):
        if record not in result:
            key = ordinal
            while key in used:
                key += 1
            result[record] = key
            used.add(key)
    return result
