"""Reference designator families: exact prefixes and trailing ASCII counters."""
from collections.abc import Callable, Iterable


_MODES = ("number", "existing", "free")


def split_refdes(reference: str) -> tuple[str, int]:
    """Return the comparison key, ignoring leading zeros in the final counter.

    Prefixes retain their exact spelling and case. An absent numeric suffix
    means zero: R, R0 and R000 have the same key. Empty/unassigned names and
    ordinary spaces are rejected. Punctuation is otherwise retained literally.
    """
    if not isinstance(reference, str):
        raise TypeError("RefDes must be text")
    if not reference:
        raise ValueError("RefDes is empty or unassigned")
    if " " in reference:
        raise ValueError("RefDes cannot contain ordinary spaces")
    prefix = reference.rstrip("0123456789")
    return prefix, int(reference[len(prefix):] or "0")


def _counter(value):
    if type(value) is not int or value < 0:
        raise ValueError("RefDes counter must be a nonnegative integer")
    return value


class RefDesFamily:
    """Search a numbered family without changing its source records.

    Ordinary iterables are captured once. A callable supplies a live collection,
    used by document views; get_refdes selects the name when items are records.
    Existing results retain spelling. Generated names use unpadded decimal digits.
    """

    def __init__(self, prefix: str, references: Iterable | Callable, *, get_refdes=None):
        if not isinstance(prefix, str):
            raise TypeError("RefDes prefix must be text")
        if " " in prefix:
            raise ValueError("RefDes prefix cannot contain ordinary spaces")
        if prefix and "0" <= prefix[-1] <= "9":
            raise ValueError("RefDes prefix cannot end with a digit; final digits belong to the counter")
        if isinstance(references, str):
            raise TypeError("references must be a collection, not one string")
        if get_refdes is not None and not callable(get_refdes):
            raise TypeError("get_refdes must be callable or None")
        self.prefix = prefix
        self._source = references if callable(references) else tuple(references)
        self._get_refdes = get_refdes

    def _entries(self):
        source = self._source() if callable(self._source) else self._source
        for item in source:
            name = self._get_refdes(item) if self._get_refdes is not None else item
            if name == "":
                continue  # Empty means unassigned, not an occupied zero.
            prefix, number = split_refdes(name)
            if prefix == self.prefix:
                yield number, name, item

    def matches(self, reference: str | None = None) -> list:
        """Return every matching item, including repeated multipart records.

        An optional reference matches its numeric identity, so R3 finds R003.
        Results follow counter, spelling, then source order for equal names.
        """
        number = None
        if reference is not None:
            prefix, number = split_refdes(reference)
            if prefix != self.prefix:
                return []
        entries = (entry for entry in self._entries() if number is None or entry[0] == number)
        return [entry[2] for entry in sorted(entries, key=lambda entry: entry[:2])]

    def designators(self) -> list[str]:
        """Return distinct authored spellings in numeric order."""
        return [name for _, name in sorted({(number, name) for number, name, _ in self._entries()})]

    def __contains__(self, reference: str) -> bool:
        try:
            prefix, number = split_refdes(reference)
        except (ValueError, TypeError):
            return False
        return prefix == self.prefix and any(entry[0] == number for entry in self._entries())

    def first(self) -> str | None:
        """Return the lowest occupied name, or None for an empty family."""
        return min(((number, name) for number, name, _ in self._entries()), default=(0, None))[1]

    def last(self) -> str | None:
        """Return the highest occupied name, or None for an empty family."""
        return max(((number, name) for number, name, _ in self._entries()), default=(0, None))[1]

    def first_free(self, start: int = 1) -> str:
        """Return an available name at or above start; this reserves nothing."""
        number = _counter(start)
        occupied = {entry[0] for entry in self._entries()}
        while number in occupied:
            number += 1
        return self.prefix + str(number)

    def _adjacent(self, reference, mode, step):
        if mode not in _MODES:
            raise ValueError(f"RefDes mode must be one of {_MODES}")
        prefix, number = split_refdes(reference)
        if prefix != self.prefix:
            raise ValueError(f"{reference!r} does not belong to RefDes family {self.prefix!r}")
        if mode == "number":
            return self.prefix + str(number + step) if number + step >= 0 else None
        entries = tuple(self._entries())
        if mode == "existing":
            choices = ((n, name) for n, name, _ in entries if (n - number) * step > 0)
            choose = min if step > 0 else max
            return choose(choices, default=(0, None))[1]
        occupied = {entry[0] for entry in entries}
        number += step
        while number >= 0 and number in occupied:
            number += step
        return self.prefix + str(number) if number >= 0 else None

    def next(self, reference: str, *, mode: str) -> str | None:
        """Find the next number, occupied name or free name, strictly after it."""
        return self._adjacent(reference, mode, 1)

    def previous(self, reference: str, *, mode: str) -> str | None:
        """Find the preceding number, occupied name or free name; stop at zero."""
        return self._adjacent(reference, mode, -1)
