"""Differential ASC output follows identities and regenerates direction caches."""
from decimal import Decimal
import unittest

from lib.common.asc import dumps, loads
from lib.common.conversion import ConversionReport, import_diagnostics
from lib.common.model import Element
from lib.common.references import Property
from lib.common.schema import MISSING
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.asc.net_projection import project_nets
from lib.pcb.formats.asc.pair_projection import project_pairs
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.model import routing_records
from lib.pcb.model.objects import new_component, new_net, new_pair, new_point, new_trace
from lib.pcb.tests.test_component_projection import design as component_design, project_input
from lib.pcb.tests.test_net_projection import signature as net_signature


def design():
    document = component_design()
    board = document.one('/Board')
    positive = board.one('Nets/Net')
    negative = board.one('Nets').append(new_net('Negative'))
    pads = board.select('Components/Component/Pattern/Pads/Pad')
    pads[1]['Net'] = negative
    traces = []
    for net, pad, sign in ((positive, pads[0], 1), (negative, pads[1], -1)):
        trace = net.one('Traces').append(new_trace())
        for x, y in ((1, 2), (3, 4)):
            point = trace.one('Points').append(new_point(x=x*sign, y=y*sign, width=.75))
            point['Layer'] = board.one('Layers/Layer[1]')
        trace['Target1'] = pad
        traces.append(trace)
    pair = board.add('DifferentialPairs').append(new_pair('Data'))
    pair['PosNet'], pair['NegNet'] = positive, negative
    row = pair.one('PadPoints').add('PadPoint')
    row['PosPad'], row['NegPad'] = pads
    segment = pair.one('Segments').add('Segment')
    segment['PosTrace'], segment['NegTrace'] = traces
    segment['Start'], segment['End'] = row, row
    centers = segment.add('CenterPoints')
    for x, y in ((10, 20), (20, 20)):
        center = centers.add('CenterPoint')
        center['X'], center['Y'] = x, y
        center['Layer'] = board.one('Layers/Layer[1]')
        for side, trace, sign in (('Pos', traces[0], 1), ('Neg', traces[1], -1)):
            center[side+'StartPoint'], center[side+'EndPoint'] = trace.one('Points').children()
            point = center.add(side+'Points').add(side+'Point')
            point['X'], point['Y'] = x, y+sign
            point['Layer'] = board.one('Layers/Layer[1]')
    center = centers.children()[0]
    traces[0].one('Points/Point[1]')['PairTarget'] = center.one('PosPoints/PosPoint')
    separate = pair.one('PosSeparateTraces').append(Element('PosTrace').bind_schema(routing_records.SEPARATE_TRACE))
    separate.add('Points').append(new_point(x=5, y=6, width=.75))
    separate['Target1'], separate['Target2'] = center.one('PosPoints/PosPoint'), pads[0]
    separate['NetTrace'] = traces[0]
    return document


def syntax(document, *, report=None):
    result = project_input(document)
    result.one('/Board/Nets').detach()
    board = result.one('/Board')
    board.append(project_nets(document.one('/Board'), report=report))
    board.append(project_pairs(document.one('/Board'), report=report))
    return result


def reopen(document, *, report=None):
    return assemble_graphics(prepare_core(dumps(syntax(document, report=report), preserve=False))).document


def signature(document):
    result = {}
    for node in document.one('/Board/DifferentialPairs').walk(include_self=True):
        if node.schema is None:
            continue
        for name, field in node.schema.fields.items():
            current = node.get(name, None if field.default is MISSING else field.default)
            if field.kind == 'reference':
                current = None if current is None else current.path
            elif field.kind == 'number' and current is not None:
                current = Decimal(str(current))
            result[node.path+'/'+name] = current
    return result


class PairProjectionTests(unittest.TestCase):
    def test_pair_geometry_ranges_pad_links_peer_links_and_point_memberships_round_trip(self):
        document = design()
        before, nets = signature(document), net_signature(document)
        rebuilt = reopen(document)
        self.assertEqual(signature(rebuilt), before)
        self.assertEqual(net_signature(rebuilt), nets)
        self.assertEqual(signature(document), before)
        self.assertEqual(signature(reopen(rebuilt)), before)
        document.references.validate()
        rebuilt.references.validate()

    def test_reordering_centers_and_pads_regenerates_selectors_and_directions(self):
        document = design()
        pair = document.one('/Board/DifferentialPairs/DifferentialPair')
        segment = pair.one('Segments/Segment')
        center = segment.one('CenterPoints/CenterPoint[1]')
        center.move_to(center.parent)
        pad = pair.one('PadPoints/PadPoint')['PosPad']
        pad.move_to(pad.parent)
        projected = project_pairs(document.one('/Board'))
        values = projected.one('DifferentialPair/PadPoints/pt').values
        self.assertEqual(values, (0, 2, 0, 1))
        centers = projected.select('DifferentialPair/Segments/Segment/CenterPoints/CenterPoint')
        self.assertEqual([row['Orientation'] for row in centers], [0, 1])
        self.assertEqual(signature(reopen(document)), signature(document))
        self.assertIsNone(center.child('Orientation'))

    def test_serialized_orientation_is_consumed_and_regenerated_from_current_coordinates(self):
        source = syntax(design())
        centers = source.select('/Board/DifferentialPairs/DifferentialPair/Segments/Segment/CenterPoints/CenterPoint')
        for center in centers:
            center.one('Orientation').set_values(999)
        document = assemble_graphics(prepare_core(dumps(source, preserve=False))).document
        current = document.one('/Board/DifferentialPairs/DifferentialPair/Segments/Segment/CenterPoints')
        self.assertTrue(all(node.child('Orientation') is None for node in current.children()))
        output = project_pairs(document.one('/Board'))
        self.assertEqual([node['Orientation'] for node in output.select(
            'DifferentialPair/Segments/Segment/CenterPoints/CenterPoint')], [0, 1])

    def test_pad_reparenting_refreshes_pair_and_net_component_observers_without_rebuilding(self):
        document = design()
        row = document.one('/Board/DifferentialPairs/DifferentialPair/PadPoints/PadPoint')
        pad = row['PosPad']
        member = document.one('/Board/Nets/Net[1]/Pads/Item')
        pair_view = document.root.add('PairComponent', -1)
        net_view = document.root.add('NetComponent', -1)
        document.references.bind(pair_view, row, Property(pair_view, 'PosComponentIndex'))
        document.references.bind(net_view, member, Property(net_view, 'ComponentIndex'))
        self.assertEqual((pair_view.values, net_view.values), ((0,), (0,)))
        other = document.one('/Board/Components').append(new_component('Second', 'U2'))
        pad.move_to(other.one('Pattern/Pads'))
        self.assertEqual((pair_view.values, net_view.values), ((1,), (1,)))
        self.assertIs(row['PosPad'], pad)
        self.assertIs(member['Pad'], pad)
        self.assertEqual(signature(reopen(document)), signature(document))
        document.references.validate()

    def test_current_unresolved_range_survives_with_a_warning(self):
        source = syntax(design())
        source.one('/Board/DifferentialPairs/DifferentialPair/Segments/Segment/CenterPoints/CenterPoint[1]/PosLine_EndPoint').set_values(100)
        reader = import_diagnostics('asc')(lambda text: assemble_graphics(prepare_core(text)).document)
        document = reader(dumps(source, preserve=False), report=ConversionReport())
        report = ConversionReport()
        rebuilt = reopen(document, report=report)
        self.assertIn('unresolved-pair-range', {notice.rule for notice in report.warnings})
        center = rebuilt.one('/Board/DifferentialPairs/DifferentialPair/Segments/Segment/CenterPoints/CenterPoint[1]')
        self.assertEqual(center['PosTrace_EndPoint'], 100)
        self.assertEqual(center['UnresolvedPosEndPointIndex'], 100)


if __name__ == '__main__':
    unittest.main()
