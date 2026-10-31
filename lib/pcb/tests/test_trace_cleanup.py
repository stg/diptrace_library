"""Import cleanup retains meaningful paths and maintains surviving identities."""
from decimal import Decimal, localcontext
from types import SimpleNamespace
import unittest

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport, import_diagnostics
from lib.pcb.formats import io
from lib.pcb.formats.assembly.routing import assemble_routing
from lib.pcb.formats.capabilities import FORMATS
from lib.pcb.model.objects import new_point, new_trace
from lib.pcb.tests.test_core_assembly import fixture
from lib.pcb.tests.test_dip_output import configured_document
from lib.pcb.tests.test_cache_projection import signature
from lib.pcb.tests.test_routing_assembly import trace


FREE = (-1, -1, -1, -1)
PAD = (0, 41, 5, -1)


def setup():
    decoded = fixture()
    net = decoded.board.one('Nets/Net')
    return decoded, net, net.add('Traces')


def geometry(item, points):
    parent = item.trace.one('Points')
    for point in tuple(parent.children()):
        point.detach()
    for index, (x, y) in enumerate(points):
        point = parent.add('Point', index)
        point.add('X', x)
        point.add('Y', y)
    return item


def load(decoded, inputs, *, report=None, other_nets=(), separate=()):
    net = decoded.board.one('Nets/Net[1]')
    decoded.upgrades = SimpleNamespace(nets=(SimpleNamespace(net=net, traces=tuple(inputs)), *other_nets),
                                      separate_traces=tuple(separate))
    assembled = []

    @import_diagnostics('asc')
    def read():
        assembled.append(assemble_routing(decoded))
        return assembled[0].document

    read(report=report)
    return assembled[0]


class TraceCleanupTests(unittest.TestCase):
    def test_short_distance_is_euclidean_strict_and_independent_of_decimal_context(self):
        cases = (((0, 0), (Decimal('.000999999999'), 0), True),
                 ((0, 0), (Decimal('.001'), 0), False),
                 ((0, 0), (Decimal('.0006'), Decimal('.0008')), False),
                 ((0, 0), (Decimal('.000599999999'), Decimal('.0008')), True),
                 ((0, 0), (Decimal('.0008'), Decimal('.0008')), False),
                 ((Decimal('1000000000'), 0),
                  (Decimal('1000000000.000999999999'), 0), True))
        for precision in (6, 28, 60):
            with localcontext() as context:
                context.prec = precision
                for first, last, removed in cases:
                    with self.subTest(precision=precision, first=first, last=last):
                        decoded, net, collection = setup()
                        item = geometry(trace(collection, 19, FREE, PAD), (first, last))
                        report = ConversionReport()
                        result = load(decoded, (item,), report=report)
                        self.assertEqual(item.trace.parent is None, removed)
                        self.assertEqual(len(result.traces), 0 if removed else 1)
                        self.assertEqual(bool([n for n in report.infos
                            if n.rule == 'unusable-trace-normalization']), removed)

    def test_connected_and_referenced_paths_keep_geometry_and_actual_targets(self):
        decoded, net, collection = setup()
        stub = geometry(trace(collection, 19, FREE, PAD), ((0, 0), (0, 0)))
        used = trace(collection, 32, (1, 73, 19, 1), PAD)
        connected = geometry(trace(collection, 44, PAD, PAD), ((0, 0), (0, 0)))
        polygonal = geometry(trace(collection, 61, FREE, PAD), ((0, 0), (0, 0), (0, 0)))
        result = load(decoded, (stub, used, connected, polygonal), report=ConversionReport())
        self.assertEqual(len(result.traces), 4)
        self.assertIs(used.trace['Target1'], stub.trace.one('Points/Point[2]'))
        self.assertEqual(stub.trace.one('Points/Point[2]')['X'], 0)
        result.document.references.validate()

    def test_invalid_point_counts_free_dependants_and_compact_current_selectors(self):
        for points in ((), ((0, 0),)):
            with self.subTest(points=points):
                decoded, net, collection = setup()
                invalid = geometry(trace(collection, 19, PAD, PAD), points)
                survivor = trace(collection, 32, (1, 73, 19, 0), PAD)
                follower = trace(collection, 44, (1, 73, 32, 1), PAD)
                result = load(decoded, (invalid, survivor, follower), report=ConversionReport())
                self.assertIsNone(invalid.trace.parent)
                self.assertIsNone(survivor.trace['Target1'])
                self.assertIs(follower.trace['Target1'], survivor.trace.one('Points/Point[2]'))
                self.assertEqual(follower.trace['SubObject1'], 0)
                self.assertEqual(set(result.traces), {(73, 32), (73, 44)})
                result.document.references.validate()

    def test_unused_short_chains_have_an_order_independent_stable_result(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                decoded, net, collection = setup()
                first = geometry(trace(collection, 19, FREE, PAD), ((0, 0), (0, 0)))
                second = geometry(trace(collection, 32, FREE, (1, 73, 19, 0)), ((0, 0), (0, 0)))
                inputs = (second, first) if reverse else (first, second)
                if reverse:
                    second.trace.move_to(collection, 0)
                result = load(decoded, inputs, report=ConversionReport())
                self.assertFalse(result.traces)
                self.assertFalse(collection.children())

    def test_removed_paths_clear_pair_selections_without_retargeting_the_next_trace(self):
        decoded, net, collection = setup()
        stub = geometry(trace(collection, 19, FREE, PAD), ((0, 0), (0, 0)))
        survivor = trace(collection, 32, PAD, PAD)
        negative = decoded.board.one('Nets').add('Net')
        for name, value in (('Number', 98), ('Enabled', True), ('Name', 'Negative')):
            negative.add(name, value)
        negative.add('Pads')
        negative.add('Traces')
        pair = decoded.board.add('DifferentialPairs').add('DifferentialPair', 0)
        for name, value in (('Number', 7), ('Enabled', True), ('Name', 'Pair'),
                            ('PosNet', 73), ('NegNet', 98)):
            pair.add(name, value)
        segment = pair.add('Segments').add('Segment', 0)
        segment.add('PosTrace', 19)
        center = segment.add('CenterPoints').add('CenterPoint', 0)
        for name, value in dict(X=0, Y=0, PosTrace_StartPoint=0, PosTrace_EndPoint=1).items():
            center.add(name, value)
        peer = trace(pair.add('PosSeparateTraces'), 61, PAD, FREE, 'PosTrace')
        peer.trace.add('TraceId', 19)
        pair.add('NegSeparateTraces')
        result = load(decoded, (stub, survivor), report=ConversionReport(), separate=(peer,),
                      other_nets=(SimpleNamespace(net=negative, traces=()),))
        self.assertIsNone(segment['PosTrace'])
        self.assertIsNone(center['PosStartPoint'])
        self.assertIsNone(center['PosEndPoint'])
        self.assertIsNone(peer.trace['NetTrace'])
        self.assertIsNone(survivor.trace['SeparateTrace'])
        self.assertEqual(survivor.trace['Id'], 0)
        result.document.references.validate()

    def test_removed_paths_discard_their_calculated_teardrop_polygons(self):
        decoded, net, collection = setup()
        stub = geometry(trace(collection, 19, FREE, PAD), ((0, 0), (0, 0)))
        stub.trace.add('ConnectedTeardrops').add('Item', 9)
        polygon = net.add('Teardrops').add('Teardrop', 9)
        polygon.add('Lay', 0)
        polygon.add('Points')
        result = load(decoded, (stub,), report=ConversionReport())
        self.assertIsNone(polygon.parent)
        self.assertNotIn((73, 9), result.core.teardrops)

    def test_every_output_profile_reimports_canonically_without_source_mutation_or_drift(self):
        document = configured_document()
        net = document.one('/Board/Nets/Net[1]')
        pad = net.one('Traces/Trace[1]')['Target1']
        stub = net.one('Traces').append(new_trace())
        for index in range(2):
            stub.one('Points').append(new_point(x=3, y=6, width=Decimal('.6')))
        stub['Target2'] = pad
        count = len(net.select('Traces/Trace'))
        before = dumps(document, preserve=False)
        for format, capability in FORMATS.items():
            for version in capability.write_versions:
                with self.subTest(format=format, version=version):
                    report = ConversionReport()
                    encoded = io.serialize(document, format=format, version=version, report=report)
                    current = io.parse(encoded, report=report)
                    self.assertEqual(len(current.select('/Board/Nets/Net[1]/Traces/Trace')), count-1)
                    self.assertEqual(len([n for n in report.notices
                        if n.rule == 'unusable-trace-normalization']), 1)
                    repeated_report = ConversionReport()
                    again = io.parse(io.serialize(current, format=format, version=version,
                        report=repeated_report), report=repeated_report)
                    self.assertFalse(any(n.rule == 'unusable-trace-normalization'
                                         for n in repeated_report.notices))
                    self.assertEqual(signature(current.root), signature(again.root))
                    current.references.validate()
        self.assertEqual(dumps(document, preserve=False), before)
