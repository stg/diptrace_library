"""Exact integer and ordered-record lookup for serialized identity selectors."""


def integer(value):
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if number == value else None


def at(items, position):
    position = integer(position)
    return items[position] if position is not None and 0 <= position < len(items) else None
