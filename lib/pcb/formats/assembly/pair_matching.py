"""Infer automatic paired-pad members from ordered, placed pad data.

This is an import calculation. It does not route traces or change geometry.
Callers supply current identities; positions and distance caches stay temporary.
"""
from dataclasses import dataclass
from functools import cache
import math


MAXIMUM_PAIR_SPAN = 100_000.


@dataclass(frozen=True)
class PadLocation:
    key: object
    x: float
    y: float
    surface: bool = False
    side: bool = False
    static_via: bool = False


def infer_members(positive, negative, *, previous=(), attached=(), limit):
    """Return ordered identity pairs, retaining routed prior associations.

    A negative pad can be consumed once. Its preferred positive is selected
    against the original positive order, so later choices do not rewrite that
    preference. Equal distances use the supplied semantic order.
    """
    positive, negative = tuple(positive), tuple(negative)
    previous = tuple(previous)
    known = {pad.key for pad in (*positive, *negative)}
    routed = set(attached) & {key for row in previous for key in row} & known
    negative_by_key = {pad.key: pad for pad in negative}
    available = set(negative_by_key)

    def distance(first, second):
        if first.key == second.key or first.surface and second.surface and first.side != second.side:
            return math.inf
        weight = 2 if first.static_via != second.static_via else 1
        return math.hypot(first.x-second.x, first.y-second.y) * weight

    def nearest(pad, choices, *, reverse=False):
        best, span = None, MAXIMUM_PAIR_SPAN
        for candidate in choices:
            measured = distance(candidate, pad) if reverse else distance(pad, candidate)
            if measured < span:
                best, span = candidate, measured
        return best, span

    @cache
    def preferred_positive(pad):
        # Cache one preference per negative pad, rather than a distance matrix.
        return nearest(pad, positive, reverse=True)[0]

    result = []
    for pad in positive:
        retained = next((negative_by_key[other] for first, other in previous
                         if first == pad.key and first in routed and other in routed
                         and other in available), None)
        if retained is not None:
            chosen, span = retained, 0.
        else:
            chosen, span = nearest(pad, (item for item in negative
                                        if item.key in available and item.key not in routed))
            if chosen is None:
                continue
            preferred = preferred_positive(chosen)
            if preferred is None or preferred.key != pad.key:
                continue
        if span < limit:
            result.append((pad.key, chosen.key))
            available.remove(chosen.key)
    return tuple(result)
