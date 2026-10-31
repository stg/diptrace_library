"""Ordinary and separate XML traces share geometry and endpoint encodings."""
from ....common.model import Element
from ....common.xml_records import enum_value, length, point
from ...model.routing_records import POINT
from ..assembly.routing_inputs import TraceInput
from ..connection_types import CONNECTION_NAMES
from ..errors import PcbError
from .keys import pad_position, position


CONNECTIONS = ('Pad', 'Trace', '2', '3', '4', 'Segment', 'Separate Trace', 'Free')
ROUTE_MODES = ('Ratlines', 'Correct Traces', 'Full Reroute', 'Dont Route')


def read_trace(record, *, units, layers, vias, version, ordinal, side=None):
    saved = record.integer('Id', ordinal)
    if saved < 0:
        saved = ordinal
    trace = Element(side+'Trace' if side is not None else 'Trace')
    for end in (1, 2):
        mode = enum_value(record.value('Connected'+str(end), 'Free'), CONNECTIONS)
        if mode not in CONNECTION_NAMES:
            raise PcbError(f'{record.node.path}: unsupported connection mode {mode}')
        trace.add('Connected'+str(end), mode)
        for name in ('Object', 'SubObject', 'Point'):
            trace.add(name+str(end), record.integer(name+str(end), -1))
    trace.add('Selected', record.boolean('Selected', False))
    trace.add('Group', record.integer('Group', -1))
    trace.add('TraceId' if side is not None else 'PairSeparateTrace',
              record.integer('TraceId' if side is not None else 'PairSeparateTrace', -1))
    points = trace.add('Points')
    for index, source in enumerate(record.rows('Points', 'Point')):
        # Point Id is an output counter. Point selectors address ordered rows,
        # including when an input omits or repeats those decorative counters.
        source.integer('Id', index)
        node = points.add('Point', index)
        for name, value in zip(('X', 'Y'), point(source, units)):
            node.add(name, value)
        for name, choices, label in (('Lay', layers, 'trace copper layer'), ('ViaStyle', vias, 'trace via style')):
            node.add(name, position(source.integer(name, -1), choices, label=label, path=source.node.path))
        if side is None:
            for name in ('PairPoint', 'PairSubPoint'):
                node.add(name, source.integer(name, 0 if name == 'PairSubPoint' else -1))
        width = -1
        if source.has('Width'):
            width = source.number('Width')
            if side is None or version.routing_metrics_in_display_units:
                width = length(width, units)
        node.add('Width', width)
        for name in ('Jumper', 'Meander', 'ShieldGroup'):
            node.add(name, source.integer(name, POINT.fields[name].default))
        for name in ('Arc', 'Selected'):
            node.add(name, source.boolean(name, False))
        node.add('PairNecked', source.boolean('Necked' if side is not None else 'PairNecked', False))
        for name in ('PhaseFwd', 'PhaseBack'):
            # Ordinary XML elides zero phase lengths. Separate traces do not
            # carry this calculation, so their missing values remain absent.
            if side is None or source.has(name):
                value = source.number(name, 0)
                node.add(name, length(value, units) if version.routing_metrics_in_display_units else value)
        node.add('MeanderAngle', source.number('MeanderAngle', 0))
        source.finish()
    if side is None:
        attached = trace.add('ConnectedTeardrops')
        for source in record.rows('ConnectedTeardrops', 'Item'):
            value = source.content()
            if value.kind != 'number' or value.unit or int(value.value) != value.value:
                raise PcbError(f'{source.node.path}: expected a teardrop key')
            attached.add('Item', int(value.value))
            source.finish(allow_text=True)
    record.finish()
    return TraceInput(trace, saved, tuple(points.children()))


def resolve_pad_endpoints(trace, placements, *, allow_missing_components=False):
    for end in (1, 2):
        suffix = str(end)
        if trace['Connected'+suffix] == 0:
            if allow_missing_components and trace['Object'+suffix] not in placements:
                # Ordinary missing-component ends are freed by shared import
                # modernization. Their pad Id has no placement to translate.
                continue
            key = pad_position(trace['Object'+suffix], trace['SubObject'+suffix], placements)
            trace.one('SubObject'+suffix).set_values(key)
