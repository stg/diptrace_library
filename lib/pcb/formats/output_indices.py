"""Generated PCB selectors over the compact current model.

Placed pad arrays in the file formats have boundary entries outside the actual
pad collection. Keep that indexing convention at the serialization boundary;
model positions and their public index views remain zero based.
"""
from .errors import PcbError
from ...common.conversion import warn
from ..model.length_matching import policy_owners


class OutputIndices:
    """One export's class order, including the format's implicit default slot."""
    def __init__(self, board):
        classes = tuple(board.select('NetClasses/NetClass'))
        default = board['DefaultClass']
        if classes and default is None:
            raise PcbError(f'{board.path}: select a default net class before export')
        if default is not None and default not in classes:
            raise PcbError(f'{board.path}: default class is outside this board')
        self.classes = (() if default is None else (default,)) + tuple(
            net_class for net_class in classes if net_class is not default)
        self._class_numbers = {net_class: index for index, net_class in enumerate(self.classes)}
        self.length_policies = policy_owners(board, classes=self.classes)
        self._length_numbers = {owner: index for index, owner in enumerate(self.length_policies)}

    def class_number(self, net_class):
        if net_class is None:
            return -1
        try:
            return self._class_numbers[net_class]
        except KeyError:
            raise PcbError(f'{net_class.path}: class is outside this export') from None

    def length_position(self, connection):
        """Locate a supplied connection in this export's class/user policy order."""
        owner = connection.parent.parent
        if owner.kind == 'LengthResults':
            owner = owner.parent
        try:
            return self._length_numbers[owner], connection._ordinal()
        except KeyError:
            raise PcbError(f'{connection.path}: length result is outside this export') from None


def pad_number(pad):
    return -1 if pad is None else pad._ordinal()+1


def pad_endpoint(row, end):
    return row['ComponentIndex'+str(end)], pad_number(row['Pad'+str(end)])


def ordered_layer_rows(rows, layers, *, uniform=False, path='layer rules'):
    """Order identity-scoped rules without retaining serialized layer slots."""
    rows = tuple(rows)
    if not rows:
        return ()
    if uniform:
        if len(rows) != 1 or rows[0]['Layer'] is not None:
            raise PcbError(f'{path}: uniform rules require one unscoped row')
        return rows
    by_layer = {row['Layer']: row for row in rows}
    if len(by_layer) != len(rows) or set(by_layer) != set(layers):
        raise PcbError(f'{path}: rules require one row per current copper layer')
    return tuple(by_layer[layer] for layer in layers)


def dimension_subobject(dimension, end):
    """Project a board dimension into a footprint array with boundary rows."""
    from ..model.graphic_records import DIMENSION
    name = 'SubObject'+str(end)
    current = dimension[name]
    if dimension.schema is not DIMENSION:
        return current
    document = dimension._owner()
    unresolved = document is not None and document.references.unresolved_slot(dimension.one(name))
    if dimension['Connected'+str(end)] in (1, 2) and not unresolved:
        current += 1
    return current


def non_signal_number(node, *, destination, report=None):
    """Project a remembered custom-layer choice, retaining its unresolved form."""
    current = node['NonSignal']
    if node.child('UnresolvedNonSignal') is not None:
        warn(report, 'unresolved-non-signal-layer', destination, 'Remembered custom-layer selection is unavailable', (node,),
             recoverability='the explicit unresolved index is retained; assign NonSignalLayer to repair it')
    return current
