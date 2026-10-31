"""Differential PCB XML from current pad, route and center identities."""
from ....common.conversion import warn
from ....common.model import Element
from ....common.xml import set_attribute
from ....common.xml_output import enum_text, field, point_attributes
from ...model import routing_records
from ...model.pair_ranges import missing_name
from ..errors import PcbError
from ..output_validation import check_tree, field_value
from .pairs import CENTER_TYPES
from .route_output import project_trace
from .routing import ROUTE_MODES


def _side_points(center, side, output, units):
    result = output.add(side+'Points')
    for source in center.select(side+'Points/'+side+'Point'):
        target = result.add(side+'Point')
        point_attributes(target, field_value(source, 'X'), field_value(source, 'Y'), units)
        for name in ('Lay', 'ViaStyle', 'Necked', 'Meander', 'MeanderAngle', 'Arc', 'Selected'):
            set_attribute(target, name, field_value(source, name))
        if field_value(source, 'ShieldGroup') >= 0:
            set_attribute(target, 'ShieldGroup', field_value(source, 'ShieldGroup'))


def _segment(segment, *, units, report):
    result = Element('Segment')
    for side in ('Pos', 'Neg'):
        set_attribute(result, side+'Trace', segment[side+'TraceIndex'])
    for end in ('Start', 'End'):
        for name in ('Point', 'Segment'):
            set_attribute(result, end+name, segment[end+name])
    centers = result.add('CenterPoints')
    for center in segment.select('CenterPoints/CenterPoint'):
        target = centers.add('CenterPoint')
        point_attributes(target, field_value(center, 'X'), field_value(center, 'Y'), units)
        for name in ('Lay', 'ViaStyle', 'PosTraceSide', 'Necked', 'Selected', 'PhaseError'):
            set_attribute(target, name, field_value(center, name))
        set_attribute(target, 'Type', enum_text(field_value(center, 'Type'), CENTER_TYPES))
        for side in ('Pos', 'Neg'):
            for end in ('Start', 'End'):
                name = side+'Trace_'+end+'Point'
                set_attribute(target, name, center[name])
            if field_value(center, side+'ShieldGroup') >= 0:
                set_attribute(target, side+'ShieldGroup', field_value(center, side+'ShieldGroup'))
            _side_points(center, side, target, units)
        if any(center.child(missing_name(side, end)) is not None
               for side in ('Pos', 'Neg') for end in ('Start', 'End')):
            warn(report, 'unresolved-pair-range', 'dipxml',
                 'Retained a differential center range whose point cannot be resolved', (center,),
                 recoverability='current range index and trace scope retained')
    return result


def project_pairs(board, *, keys, units, display_metrics=True, report=None, removed=False):
    kind = 'RemovedDifferentialPair' if removed else 'DifferentialPair'
    schema = routing_records.REMOVED_PAIR if removed else routing_records.PAIR
    result = Element(kind+'s')
    for pair in board.select(kind+'s/'+kind):
        check_tree(pair, schema, destination='DIPXML')
        if not removed and not field_value(pair, 'Enabled'):
            raise PcbError(f'{pair.path}: inactive pair needs output normalization')
        if pair['PosNet'] is None or pair['NegNet'] is None:
            raise PcbError(f'{pair.path}: differential pair requires both nets before export')
        target = result.add(kind)
        for name, value in (('Id', pair['Id']), ('PosNet', pair['PosNetIndex']),
                            ('NegNet', pair['NegNetIndex']), ('NetClass', keys.net_class(pair['Class']))):
            set_attribute(target, name, value)
        if removed:
            set_attribute(target, 'Enabled', field_value(pair, 'Enabled'))
        else:
            set_attribute(target, 'RouteMode', enum_text(field_value(pair, 'RouteMode'), ROUTE_MODES))
            set_attribute(target, 'AutoPadPoints', field_value(pair, 'AutoPadPoints'))
        for name in ('CustomColor', 'TraceColor'):
            set_attribute(target, name, field_value(pair, name))
        field(target, 'Name', field_value(pair, 'Name'))
        pads = target.add('PadPoints')
        for source in pair.select('PadPoints/PadPoint'):
            row = pads.add('PadPoint')
            set_attribute(row, 'Id', source['Id'])
            for side in ('Pos', 'Neg'):
                component, pad = keys.pad(source[side+'Pad'])
                set_attribute(row, side+'Comp', component)
                set_attribute(row, side+'Pad', pad)
        segments = target.add('Segments')
        for segment in pair.select('Segments/Segment'):
            segments.append(_segment(segment, units=units, report=report))
        for side in (() if removed else ('Pos', 'Neg')):
            traces = target.add(side+'SeparateTraces')
            for trace in pair.select(side+'SeparateTraces/'+side+'Trace'):
                traces.append(project_trace(trace, keys=keys, units=units, display_metrics=display_metrics, report=report))
    return result
