"""Named routing geometry and identity-based endpoint access."""
from ...common.schema import Child, Field, Record
from . import routing, pair_routing, pair_membership, pair_ranges
from .relationships import reference_field, index_field
from .membership import component_of, component_inputs
from .board_rules import LAYER_FIELDS, VIA_FIELDS, CLASS_FIELDS
from .graphic_records import GROUP_FIELDS
from .teardrops import MEMBERS as TRACE_TEARDROPS


def _ordinal(name='Id'):
    return Field(name, 'integer', getter=lambda node: node._ordinal(),
                 ordinal_dependencies=lambda node: (node,))


def _endpoint_fields(end):
    role = routing.ENDS[end-1]
    dependencies = lambda trace: ((trace, role, 'outgoing'),)
    return {
        'Target'+str(end): reference_field('Target'+str(end), role),
        'Connected'+str(end): Field('Connected'+str(end), 'text',
            getter=lambda trace: routing.endpoint_kind(routing.linked(trace, role)),
            ordinal_dependencies=lambda trace: routing.endpoint_ordinals(trace, end),
            reference_dependencies=dependencies),
        **{name+str(end): Field(name+str(end), 'integer',
            getter=lambda trace, index=index: routing.endpoint_values(trace, end)[index],
            ordinal_dependencies=lambda trace: routing.endpoint_ordinals(trace, end),
            reference_dependencies=dependencies)
           for index, name in enumerate(('Object', 'SubObject', 'Point'))},
    }


TRACE_FIELDS = {'Id': _ordinal(), **_endpoint_fields(1), **_endpoint_fields(2),
    'Selected': Field('Selected', 'boolean', default=False),
    **GROUP_FIELDS,
}
_PEER_DEPENDENCIES = lambda trace: ((trace, pair_routing.PEER, 'incoming'),)
TRACE = Record('PcbTrace', {**TRACE_FIELDS,
    'SeparateTrace': Field('SeparateTrace', 'reference', nullable=True, getter=pair_routing.separate_peer,
                          reference_dependencies=_PEER_DEPENDENCIES),
    'PairSeparateTrace': Field('PairSeparateTrace', 'integer',
        getter=lambda trace: peer._ordinal() if (peer := pair_routing.separate_peer(trace)) is not None else -1,
        reference_dependencies=_PEER_DEPENDENCIES,
        ordinal_dependencies=lambda trace: (peer,) if (peer := pair_routing.separate_peer(trace)) is not None else ()),
}, parameters=('Id',), children={
    'Points': Child('Points', 'PcbTracePoints', minimum=1),
    'ConnectedTeardrops': Child('ConnectedTeardrops', TRACE_TEARDROPS.name),
})
SEPARATE_TRACE = Record('PcbSeparateTrace', {**TRACE_FIELDS,
    'NetTrace': reference_field('NetTrace', pair_routing.PEER),
    'TraceId': index_field('TraceId', pair_routing.PEER),
}, parameters=('Id',), children={name: child for name, child in TRACE.children.items()
                               if name != 'ConnectedTeardrops'})
POINT_FIELDS = {
    **LAYER_FIELDS, **VIA_FIELDS,
    'Id': _ordinal(),
    **{name: Field(name, 'number', required=True, default=0, unit='shared length') for name in ('X', 'Y')},
    'Width': Field('Width', 'number', default=-1, unit='shared length'),
    **{name: Field(name, 'integer', default=default) for name, default in
       (('Jumper', 0), ('Meander', 0), ('ShieldGroup', -1))},
    'PairTarget': reference_field('PairTarget', pair_membership.ROLE),
    **{name: Field(name, 'integer', getter=lambda point, i=i: pair_membership.values(point)[i],
        reference_dependencies=lambda point: ((point, pair_membership.ROLE, 'outgoing'),),
        ordinal_dependencies=pair_membership.ordinals)
       for i, name in enumerate(('PairPoint', 'PairSubPoint'))},
    **{name: Field(name, 'boolean', default=False) for name in ('Arc', 'Selected', 'PairNecked')},
    **{name: Field(name, 'number', nullable=True, default=None, unit='shared length',
                  description='Calculated phase length, absent when unavailable.')
       for name in ('PhaseFwd', 'PhaseBack')},
    'MeanderAngle': Field('MeanderAngle', 'number', default=0),
}
POINT = Record('PcbTracePoint', POINT_FIELDS, parameters=('Id',))
SIDE_POINT = Record('PcbPairSidePoint', {
    **{name: field for name, field in POINT_FIELDS.items()
       if name not in ('Width', 'Jumper', 'PairTarget', 'PairPoint', 'PairSubPoint', 'PairNecked', 'PhaseFwd', 'PhaseBack')},
    'Necked': Field('Necked', 'boolean', default=False),
}, parameters=('Id',))


def _paired_pad_fields(side, role):
    def pad(row):
        return routing.linked(row, role)

    dependencies = lambda row: ((row, role, 'outgoing'),)
    return {
        side+'Pad': reference_field(side+'Pad', role),
        side+'ComponentIndex': Field(side+'ComponentIndex', 'integer',
            getter=lambda row: component_of(target)._ordinal() if (target := pad(row)) is not None else -1,
            reference_dependencies=dependencies,
            ordinal_dependencies=lambda row: component_inputs(pad(row))),
        side+'PadIndex': Field(side+'PadIndex', 'integer',
            getter=lambda row: target._ordinal() if (target := pad(row)) is not None else -1,
            reference_dependencies=dependencies,
            ordinal_dependencies=lambda row: (target,) if (target := pad(row)) is not None else ()),
    }


PAIRED_PAD = Record('PcbPairedPad', {'Id': _ordinal(),
    **{name: field for role, side in routing.PAIRED_PADS.items()
       for name, field in _paired_pad_fields(side, role).items()},
}, parameters=('Id',))
PAIR = Record('PcbDifferentialPair', {
    **CLASS_FIELDS,
    'Id': _ordinal(),
    'Name': Field('Name', 'text', default=''),
    'Enabled': Field('Enabled', 'boolean', default=True),
    'CustomColor': Field('CustomColor', 'boolean', default=False),
    'TraceColor': Field('TraceColor', 'integer', default=0),
    'AutoPadPoints': Field('AutoPadPoints', 'boolean', default=True),
    'RouteMode': Field('RouteMode', 'integer', default=0),
    'PosNet': reference_field('PosNet', 'pair-positive'), 'NegNet': reference_field('NegNet', 'pair-negative'),
    **{side+'NetIndex': Field(side+'NetIndex', 'integer',
        getter=lambda pair, side=side: net._ordinal() if (net := routing.pair_net(pair, side)) is not None else -1,
        ordinal_dependencies=lambda pair, side=side: (net,) if (net := routing.pair_net(pair, side)) is not None else (),
        reference_dependencies=lambda pair, role=role: ((pair, role, 'outgoing'),))
       for side, role in (('Pos', 'pair-positive'), ('Neg', 'pair-negative'))},
}, parameters=('Id',), children={
    'PadPoints': Child('PadPoints', 'PcbPairedPads'),
    'Segments': Child('Segments', 'PcbPairSegments'),
    'PosSeparateTraces': Child('PosSeparateTraces', 'PcbPositiveTraces'),
    'NegSeparateTraces': Child('NegSeparateTraces', 'PcbNegativeTraces'),
})
REMOVED_PAIR = Record('PcbRemovedDifferentialPair', {
    name: field for name, field in PAIR.fields.items() if name not in ('AutoPadPoints', 'RouteMode')
}, parameters=PAIR.parameters, children={name: child for name, child in PAIR.children.items()
                                       if name not in ('PosSeparateTraces', 'NegSeparateTraces')})
def _segment_end_fields(role, end):
    dependencies = lambda segment: ((segment, role, 'outgoing'),)
    ordinals = lambda segment: pair_routing.segment_end_ordinals(segment, role)
    return {
        end: reference_field(end, role),
        **{end+name: Field(end+name, 'integer',
            getter=lambda segment, i=i: pair_routing.segment_end_values(segment, role)[i],
            reference_dependencies=dependencies, ordinal_dependencies=ordinals)
           for i, name in enumerate(('Point', 'Segment'))},
    }


SEGMENT = Record('PcbPairSegment', {'Id': _ordinal(),
    **{name: field for role, end in pair_routing.SEGMENT_ENDS.items()
       for name, field in _segment_end_fields(role, end).items()},
    **{name: field for role, side in pair_routing.SEGMENT_TRACES.items()
       for name, field in ((side+'Trace', reference_field(side+'Trace', role)),
                           (side+'TraceIndex', index_field(side+'TraceIndex', role)))},
}, parameters=('Id',), children={
    'CenterPoints': Child('CenterPoints', 'PcbPairCenters', minimum=1),
})
CENTER = Record('PcbPairCenter', {'Id': _ordinal(),
    **LAYER_FIELDS, **VIA_FIELDS,
    **{name: Field(name, 'number', required=True, default=0, unit='shared length') for name in ('X', 'Y')},
    'Type': Field('Type', 'integer', default=0),
    'PosTraceSide': Field('PosTraceSide', 'integer', default=-1),
    **{side+'ShieldGroup': Field(side+'ShieldGroup', 'integer', default=-1) for side in ('Pos', 'Neg')},
    **{name: field for role, (side, end) in pair_routing.RANGES.items()
       for name, field in pair_ranges.fields(role, side, end).items()},
    **{name: Field(name, 'boolean', default=False) for name in ('Necked', 'Selected', 'PhaseError')},
}, parameters=('Id',), children={
    'PosPoints': Child('PosPoints', 'PcbPositivePoints'),
    'NegPoints': Child('NegPoints', 'PcbNegativePoints'),
})


def _collection(name, child, record):
    return Record(name, {}, children={child: Child(child, record, maximum=None)})


COLLECTIONS = {
    'Traces': _collection('PcbTraces', 'Trace', TRACE.name),
    'Points': _collection('PcbTracePoints', 'Point', POINT.name),
    'DifferentialPairs': _collection('PcbDifferentialPairs', 'DifferentialPair', PAIR.name),
    'RemovedDifferentialPairs': _collection('PcbRemovedDifferentialPairs', 'RemovedDifferentialPair', REMOVED_PAIR.name),
    'PadPoints': _collection('PcbPairedPads', 'PadPoint', PAIRED_PAD.name),
    'Segments': _collection('PcbPairSegments', 'Segment', SEGMENT.name),
    'CenterPoints': _collection('PcbPairCenters', 'CenterPoint', CENTER.name),
    'PosPoints': _collection('PcbPositivePoints', 'PosPoint', SIDE_POINT.name),
    'NegPoints': _collection('PcbNegativePoints', 'NegPoint', SIDE_POINT.name),
    'PosSeparateTraces': _collection('PcbPositiveTraces', 'PosTrace', SEPARATE_TRACE.name),
    'NegSeparateTraces': _collection('PcbNegativeTraces', 'NegTrace', SEPARATE_TRACE.name),
}


def definition(node):
    parent = node.parent
    if parent is None:
        return None
    if node.kind == 'Traces' and parent.kind == 'Net':
        return COLLECTIONS[node.kind]
    if node.kind == 'Trace' and parent.kind == 'Traces':
        return TRACE
    if node.kind == 'Points' and parent.kind in ('Trace', 'PosTrace', 'NegTrace'):
        return COLLECTIONS['Points']
    if (node.kind == 'Point' and parent.kind == 'Points' and routing.point_trace(node) is not None and
            routing.point_trace(node).kind in ('Trace', 'PosTrace', 'NegTrace')):
        return POINT
    if node.kind == 'DifferentialPairs' and parent.kind == 'Board':
        return COLLECTIONS['DifferentialPairs']
    if node.kind == 'DifferentialPair' and parent.kind == 'DifferentialPairs':
        return PAIR
    if node.kind == 'RemovedDifferentialPairs' and parent.kind == 'Board':
        return COLLECTIONS['RemovedDifferentialPairs']
    if node.kind == 'RemovedDifferentialPair' and parent.kind == 'RemovedDifferentialPairs':
        return REMOVED_PAIR
    if node.kind == 'PadPoints' and routing.is_pair(parent):
        return COLLECTIONS['PadPoints']
    if node.kind == 'PadPoint' and parent.kind == 'PadPoints' and routing.pad_pair(node) is not None:
        return PAIRED_PAD
    if (node.kind == 'Segments' and routing.is_pair(parent) or
            node.kind in ('PosSeparateTraces', 'NegSeparateTraces') and parent.kind == 'DifferentialPair'):
        return COLLECTIONS[node.kind]
    if node.kind == 'Segment' and parent.kind == 'Segments' and routing.is_pair(routing.ancestor(node, 2)):
        return SEGMENT
    if node.kind == 'CenterPoints' and parent.kind == 'Segment':
        return COLLECTIONS[node.kind]
    if node.kind == 'CenterPoint' and parent.kind == 'CenterPoints':
        return CENTER
    if node.kind in ('PosPoints', 'NegPoints') and parent.kind == 'CenterPoint':
        return COLLECTIONS[node.kind]
    if node.kind in ('PosPoint', 'NegPoint') and parent.kind == node.kind[:3]+'Points':
        return SIDE_POINT
    if node.kind in ('PosTrace', 'NegTrace') and parent.kind == node.kind[:3]+'SeparateTraces':
        return SEPARATE_TRACE
    return None
