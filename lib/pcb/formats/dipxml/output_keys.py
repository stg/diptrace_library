"""One XML export's identity maps, outside authored model data."""
from ..errors import PcbError
from ..output_indices import OutputIndices


class OutputKeys:
    def __init__(self, board, library):
        self.indices = OutputIndices(board)
        self._members = {name: {} for name in ('pad', 'shape', 'hole')}
        for pattern, style in library.physical_styles.items():
            component = pattern.parent
            if component is not None and component.kind == 'Component':
                for name in self._members:
                    for member, key in getattr(style, name+'_keys').items():
                        self._members[name][member] = component['Number'], key

    def _member(self, kind, member):
        if member is None:
            return -1, -1
        try:
            return self._members[kind][member]
        except KeyError:
            raise PcbError(f'{member.path}: {kind} has no placed physical XML key') from None

    def pad(self, pad):
        return self._member('pad', pad)

    def shape(self, shape):
        return self._member('shape', shape)

    def hole(self, hole):
        return self._member('hole', hole)

    def net_class(self, net_class):
        return self.indices.class_number(net_class)
