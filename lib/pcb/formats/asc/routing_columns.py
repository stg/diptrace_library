"""ASC routing row dialects shared by readers and writers.

Compatibility columns belong to these serializations, not the editable model.
"""
POINT = ('X', 'Y', 'Lay', 'Direction', 'Width', 'ViaSize', 'ViaRing', 'Jumper',
         'ThroughVia', 'Arc', 'ViaStyle', 'ViaHole', 'ViaFrom', 'ViaTo', 'Selected',
         'PairPoint', 'PhaseFwd', 'PhaseBack', 'PairSubPoint', 'PairNecked', 'Meander', 'MeanderAngle')
SEPARATE_POINT = ('X', 'Y', 'Lay', 'Direction', 'Width', 'ViaSize', 'ThroughVia',
                  'Jumper', 'Arc', 'ViaStyle', 'ViaHole', 'ViaFrom', 'ViaTo',
                  'Selected', 'PairNecked', 'Meander', 'MeanderAngle')
SIDE_POINT = ('X', 'Y', 'Selected', 'Lay', 'ViaStyle', 'Necked', 'Meander', 'MeanderAngle', 'Arc')
COMPATIBILITY = frozenset(('Direction', 'ViaSize', 'ViaRing', 'ThroughVia', 'ViaHole', 'ViaFrom', 'ViaTo'))
FLAGS = frozenset(('ThroughVia', 'Arc', 'Selected', 'PairNecked', 'Necked'))
INTEGERS = frozenset(('Lay', 'Direction', 'Jumper', 'ViaStyle', 'ViaFrom', 'ViaTo',
                      'PairPoint', 'PairSubPoint', 'Meander'))


def indices(columns, names):
    return tuple(index for index, name in enumerate(columns) if name in names)
