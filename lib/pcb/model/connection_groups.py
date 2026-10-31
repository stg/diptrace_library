"""Derived component-local pad connectivity and its display geometry.

Labels and authored pair definitions are the inputs. Group membership and
ratlines are calculated views; neither is an additional authored connection.
"""
from decimal import Decimal

from ...common.references import ReferenceError


FIDUCIAL_SHAPE = 20
_LABEL_IGNORED = str.maketrans('', '', ' @')


def pad_label_key(label):
    """Return the case-sensitive electrical label, ignoring spaces and @."""
    return label.translate(_LABEL_IGNORED)


def groups(component, *, strict=True):
    """Return connected pad tuples in current pad order, without changing data.

    Equal electrical labels join non-fiducial pads. Authored definitions join
    their explicit targets independently of labels. Unconnected single pads do
    not form groups; an explicit self-pair still defines a participating pad.
    Work is local to this component and linear apart from disjoint-set lookup.
    """
    pads = component.select('Pattern/Pads/Pad')
    positions = {pad: index for index, pad in enumerate(pads)}
    parents = list(range(len(pads)))
    sizes = [1]*len(pads)
    participating = set()

    def root(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def join(first, second):
        participating.update((first, second))
        first, second = root(first), root(second)
        if first != second:
            if sizes[first] < sizes[second]:
                first, second = second, first
            parents[second] = first
            sizes[first] += sizes[second]

    labels = {}
    for index, pad in enumerate(pads):
        if pad['PadShape_New'] == FIDUCIAL_SHAPE:
            continue
        key = pad_label_key(pad['StringNumber'])
        if key in labels:
            join(labels[key], index)
        else:
            labels[key] = index
    for pair in component.select('IntConRecords/Item'):
        first, second = pair['Pad1'], pair['Pad2']
        if first not in positions or second not in positions:
            if strict:
                raise ReferenceError('internal connection definition requires two local pad targets')
            continue
        join(positions[first], positions[second])
    selected = {}
    for index, pad in enumerate(pads):
        if index in participating:
            selected.setdefault(root(index), []).append(pad)
    return tuple(tuple(members) for members in selected.values())


def ratlines(pads):
    """Calculate a deterministic minimum spanning tree of pad identities.

    This is connection-display geometry, not copper routing. Exact integer-grid
    distances avoid rounding and memory use stays linear in pads.
    Equal choices follow the supplied order. Existing pad geometry is untouched.
    """
    pads = tuple(pads)
    if len(pads) < 2:
        return ()
    if len(set(pads)) != len(pads):
        raise ValueError('ratline group contains duplicate pads')
    values = [Decimal(str(pad[name])).as_tuple() for pad in pads for name in ('X', 'Y')]
    exponent = min(value.exponent for value in values)
    integers = []
    for value in values:
        coefficient = 0
        for digit in value.digits:
            coefficient = coefficient*10+digit
        integers.append((-coefficient if value.sign else coefficient)*10**(value.exponent-exponent))
    coordinates = tuple(zip(integers[::2], integers[1::2]))

    def distance(first, second):
        a, b = coordinates[first], coordinates[second]
        return (a[0]-b[0])**2 + (a[1]-b[1])**2

    remaining = {index: (distance(0, index), 0) for index in range(1, len(pads))}
    edges = []
    while remaining:
        next_pad = min(remaining, key=lambda index: (remaining[index][0], index))
        _, previous = remaining.pop(next_pad)
        edges.append((pads[previous], pads[next_pad]))
        for index, best in remaining.items():
            candidate = distance(next_pad, index), next_pad
            if candidate[0] < best[0]:
                remaining[index] = candidate
    return tuple(edges)
