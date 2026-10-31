"""ASC routing output uses current identities, geometry and via settings."""
from decimal import Decimal
import unittest

from lib.common.asc import dumps, loads
from lib.common.conversion import ConversionReport
from lib.common.schema import MISSING
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.asc.net_projection import project_nets, project_trace
from lib.pcb.formats.asc.routing import unpack_trace
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.formats.errors import PcbError
from lib.pcb.formats.routing_projection import point_directions
from lib.pcb.model.objects import new_point, new_trace
from lib.pcb.tests.test_component_projection import design as component_design, project_input
from lib.pcb.tests.test_asc_differential_pairs import design as pair_source


def design():
    document = component_design()
    net = document.one('/Board/Nets/Net')
    trace = net.one('Traces').append(new_trace())
    for x, y in ((1, 2), (3, 4), (5, 4)):
        point = trace.one('Points').append(new_point(x=x, y=y, width=.75))
        point['Layer'] = document.one('/Board/Layers/Layer[1]')
    trace['Target1'] = document.one('/Board/Components/Component/Pattern/Pads/Pad[1]')
    trace['Target2'] = document.one('/Board/Components/Component/Pattern/Pads/Pad[2]')
    return document


def reopen(document, *, report=None):
    syntax = project_input(document)
    syntax.one('/Board/Nets').detach()
    syntax.one('/Board').append(project_nets(document.one('/Board'), report=report))
    return assemble_graphics(prepare_core(dumps(syntax, preserve=False))).document


def signature(document):
    result = {}
    for node in document.one('/Board/Nets').walk(include_self=True):
        if node.schema is None:
            continue
        for name, definition in node.schema.fields.items():
            current = node.get(name, None if definition.default is MISSING else definition.default)
            if definition.kind == 'reference':
                current = None if current is None else current.path
            elif definition.kind == 'number' and current is not None:
                current = Decimal(str(current))
            result[node.path+'/'+name] = current
    return result


class NetProjectionTests(unittest.TestCase):
    def test_current_net_and_trace_data_round_trip_without_mutating_the_source(self):
        document = design()
        net = document.one('/Board/Nets/Net')
        for name, current in dict(Width=1.25, Clearance=.6, MeanderGap=2.5, RouteMode=2,
                                  Locked=True, Highlighted=True, ShowLength=True,
                                  HideRatlines=True, CustomColor=True, TraceColor=0x123456).items():
            net[name] = current
        point = net.one('Traces/Trace/Points/Point[2]')
        for name, current in dict(Jumper=2, Arc=True, Selected=True, PairNecked=True,
                                  Meander=3, MeanderAngle=.37, PhaseFwd=12.5).items():
            point[name] = current
        before = signature(document)
        rebuilt = reopen(document)
        self.assertEqual(signature(rebuilt), before)
        self.assertEqual(signature(document), before)
        self.assertEqual(signature(reopen(rebuilt)), before)
        document.references.validate()
        rebuilt.references.validate()

    def test_endpoint_and_membership_indices_follow_current_pad_trace_and_point_order(self):
        document = design()
        net = document.one('/Board/Nets/Net')
        first = net.one('Traces/Trace')
        target = first.one('Points/Point[2]')
        second = net.one('Traces').append(new_trace())
        second.one('Points').append(new_point(x=8, y=9))
        second.one('Points').append(new_point(x=10, y=9))
        second['Target1'] = target
        pad = first['Target1']
        pad.move_to(pad.parent)
        target.move_to(target.parent, 0)
        first.move_to(first.parent)
        projected = project_nets(document.one('/Board'))
        line = projected.one('Net/Lines/Line[1]')
        self.assertEqual((line['Connect1'], line['ConnectL1'], line['ConnectP1']), (0, 1, 0))
        self.assertEqual(line['ConnectMode2'], -1)
        rebuilt = reopen(document)
        rebuilt_first = rebuilt.one('/Board/Nets/Net/Traces/Trace[1]')
        self.assertEqual(rebuilt_first['Target1'].path, target.path)
        self.assertEqual(signature(rebuilt), signature(document))

    def test_via_echoes_are_regenerated_from_style_dimensions_and_identity_span(self):
        document = design()
        board = document.one('/Board')
        style = board.one('ViaStyles/ViaStyle')
        point = board.one('Nets/Net/Traces/Trace/Points/Point[2]')
        point['Via'] = style
        style['Size'], style['HoleSize'] = 3.5, 1.5
        style['Span'] = (board.one('Layers/Layer[1]'), board.one('Layers/Layer[2]'))
        projected = project_nets(board)
        net = projected.one('Net')
        self.assertEqual((net['ViaSize'], net['ViaRing'], net['ThroughVia']), (3.5, 1, 'N'))
        row = net.one('Lines/Line/Points/pt[2]').values
        self.assertEqual((row[5], row[6], row[8], row[10:14]), (3.5, 1, 'N', (0, 1.5, 0, 1)))
        style['Size'] = 5.5
        self.assertEqual(project_nets(board).one('Net/Lines/Line/Points/pt[2]').values[5], 5.5)
        rebuilt = reopen(document)
        self.assertEqual(signature(rebuilt), signature(document))
        self.assertIsNone(point.child('ViaSize'))

    def test_unavailable_phase_and_unselected_via_use_compatibility_values_only(self):
        document = design()
        point = document.one('/Board/Nets/Net/Traces/Trace/Points/Point[1]')
        self.assertIsNone(point['Via'])
        self.assertIsNone(point['PhaseFwd'])
        del point['Arc']  # Removing an optional value uses its declared export default.
        row = project_nets(document.one('/Board')).one('Net/Lines/Line/Points/pt[1]').values
        self.assertEqual((row[5:7], row[8], row[10:14], row[16:18]),
                         ((0, 0), 'N', (-1, 0, -1, -1), (-100_000, -100_000)))
        rebuilt = reopen(document)
        self.assertIsNone(rebuilt.one(point.path).get('PhaseFwd'))
        self.assertIsNone(point.child('ViaSize'))
        self.assertIsNone(point.child('Direction'))

    def test_direction_codes_classify_geometry_without_snapping_it(self):
        cases = (((0, 0), (5, 0), 1), ((0, 0), (0, 5), 2),
                 ((0, 0), (5, 5), 3), ((0, 0), (5, -5), 4),
                 ((0, 0), (5, 2), 0), ((0, 0), (0, 0), 0),
                 ((0, 0), (30, .49), 1), ((0, 0), (30, .51), 0))
        for start, end, expected in cases:
            with self.subTest(end=end):
                points = [new_point(x=x, y=y) for x, y in (start, end)]
                self.assertEqual(list(point_directions(points)), [0, expected])
                self.assertEqual((points[1]['X'], points[1]['Y']), tuple(Decimal(str(x)) for x in end))
        points = [new_point(x=x, y=y) for x, y in ((0, 0), (10, 0), (20, .1), (30, .1))]
        points[1]['Arc'] = True
        self.assertEqual(list(point_directions(points)), [0, 0, 0, 1])
        points[3]['Y'] = .2
        self.assertEqual(list(point_directions(points)), [0, 0, 0, 0])

    def test_separate_trace_uses_its_17_column_dialect_and_current_peer_endpoint_indices(self):
        syntax = loads(pair_source())
        context = project_input(component_design())
        for name in ('Layers', 'ViaStyles'):
            context.one('/Board/'+name).move_to(syntax.one('/Board'))
        document = assemble_graphics(prepare_core(dumps(syntax, preserve=False))).document
        trace = document.one('/Board/DifferentialPairs/DifferentialPair/PosSeparateTraces/PosTrace')
        output = project_trace(trace, separate=True)
        self.assertEqual(output.kind, 'Line_Pos')
        self.assertEqual((output['ConnectMode1'], output['ConnectMode2']), (5, 0))
        self.assertEqual((output['ConnectL2'], output['ConnectP2']), (1, -1))
        self.assertEqual(output['NetLine_Link'], 0)
        row = output.one('Points/Point')
        self.assertEqual(len(row.values), 17)
        self.assertEqual((row.values[6], row.values[7], row.values[8]), ('N', 2, 'N'))
        prepared = unpack_trace(output, separate=True)
        self.assertEqual(prepared.trace['TraceId'], 0)
        self.assertEqual(prepared.points[0]['Jumper'], 2)
        self.assertFalse(prepared.points[0]['Arc'])

    def test_supplied_teardrop_geometry_and_trace_membership_survive_reordering(self):
        document = design()
        net = document.one('/Board/Nets/Net')
        polygon = net.add('Teardrops').add('Teardrop')
        polygon['Layer'] = document.one('/Board/Layers/Layer[1]')
        polygon['DrawX'], polygon['DrawY'] = 3, 4
        points = polygon.add('Points')
        for xy in ((1, 2), (4, 5), (7, 2)):
            points.add('pt', *xy)
        trace = net.one('Traces/Trace')
        item = trace.add('ConnectedTeardrops').add('Item')
        item['Teardrop'] = polygon
        rebuilt = reopen(document)
        self.assertEqual(signature(rebuilt), signature(document))
        self.assertEqual(rebuilt.one(polygon.path).one('Points/pt[2]').values, (4, 5))
        self.assertIs(rebuilt.one(item.path)['Teardrop'], rebuilt.one(polygon.path))

    def test_known_asc_omissions_warn_and_unmapped_content_is_an_error(self):
        document = design()
        net = document.one('/Board/Nets/Net')
        point = net.one('Traces/Trace/Points/Point[1]')
        net['HiddenId'], net['AllowLoops'], point['ShieldGroup'] = 42, True, 7
        report = ConversionReport()
        rebuilt = reopen(document, report=report)
        self.assertEqual({notice.rule for notice in report.warnings},
                         {'net-update-key', 'net-loop-setting', 'trace-shield-group'})
        self.assertEqual((net['HiddenId'], net['AllowLoops'], point['ShieldGroup']), (42, True, 7))
        self.assertEqual(rebuilt.one(net.path).get('HiddenId', 0), 0)
        net.one('Traces/Trace').add('Unmapped', 123)
        with self.assertRaisesRegex(PcbError, 'no PCB ASC projection'):
            project_nets(document.one('/Board'), report=report)


if __name__ == '__main__':
    unittest.main()
