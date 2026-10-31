"""Named XML via-style data and its static-via footprint instantiation."""
from decimal import Decimal

from ....common.xml_records import length
from ....common.xml_footprints import ImportedPattern
from ....common.footprint_objects import new_pad
from ....common.conversion import import_notice
from ...model.static_via import pad_geometry
from ..errors import PcbError
from .patterns import POLICY
from .keys import unique_id
from .pad_options import read_pad_options


def read_vias(record, board, *, units, layer_count):
    collection, by_key = board.add('ViaStyles'), {}
    for source in record.rows('ViaStyles', 'ViaStyle'):
        key = unique_id(source, by_key, label='via style')
        # XML describes a span by its copper-stack positions, rather than a
        # Through flag or layer IDs. Both outside positions imply a full span.
        first, last = source.integer('Lay1', 0), source.integer('Lay2', -1)
        through = first == 0 and (last < 0 or last == layer_count-1)
        by_key[key] = collection.add('ViaStyle', source.text('Name', ''), through,
            length(source.number('Size'), units), length(source.number('HoleSize'), units),
            first, last)
        source.finish()
    return by_key


def implicit_via_pattern(style):
    """Prepare missing footprint defaults; placement entries supply the pads."""
    _name, _through, size, hole, _first, _last = style.values
    pattern = POLICY.pattern_factory('')
    for name, value in dict(Type=16, Mounting=0, Width=size, Height=size, PadWidth=size, PadHeight=size,
                            PadHole=hole, PadHoleH=hole).items():
        pattern.set_field(name, value)
    for index in range(2):
        pattern.one('Shapes').append(POLICY.drawing_factory(index))
        pattern.one('Holes').add('Hole', False, False, 0, 0, 0, 0, -1)
    return ImportedPattern(pattern, {}, {}, {}, set())


def read_via_pads(record, pattern, *, units, layers=None):
    """Instantiate placement pads instead of inheriting physical-template pads.

    Public keys identify connections; generated labels use current row order.
    The selected via style supplies dimensions during shared import assembly.
    """
    pads = pattern.one('Pads')
    for pad in tuple(pads.children()):
        pad.detach()
    pads.append(POLICY.pad_factory(0))
    positions = {}
    for ordinal, source in enumerate(record.rows('Pads', 'Pad'), 1):
        key = source.integer('Id', -1)
        if key >= 0:
            if key in positions:
                raise PcbError(f'{source.node.path}: duplicate placed via pad {key}')
            positions[key] = ordinal
        pad = pads.append(new_pad(str(ordinal), index=ordinal))
        pad['Number_New'] = ordinal
        for name, value in pad_geometry(-1, Decimal('.5')).items():
            pad[name] = value
        pad.add('NetNumber', source.integer('NetId', -1))
        pad.add('InternalConnection', source.integer('InternalConnection', -1))
        read_pad_options(source, pad, units=units, layers=layers)
        source.finish()
    pads.append(POLICY.pad_factory(len(pads.children())))
    import_notice('info', 'xml-via-pad-initialization',
                  'Initialized XML via pads from placement entries rather than template pad data.',
                  (pattern,), recoverability='pad connections and placed options remain; public keys regenerate on output')
    return positions
