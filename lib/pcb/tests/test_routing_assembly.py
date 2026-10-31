"""Saved trace keys and obsolete endpoint slots are consumed during import."""
from types import SimpleNamespace
import unittest

from lib.pcb.formats.assembly.routing import assemble_routing
from lib.pcb.tests.test_core_assembly import fixture


def trace(collection, key, first, second, kind='Trace'):
    node = collection.add(kind, 0)
    for end, values in enumerate((first, second), 1):
        for name, value in zip(('Connected', 'Object', 'SubObject', 'Point'), values):
            node.add(name+str(end), value)
    points = node.add('Points')
    for index in range(2):
        point = points.add('Point', index)
        point.add('X', index)
        point.add('Y', 0)
    return SimpleNamespace(trace=node, previous_number=key, points=())


class RoutingAssemblyTests(unittest.TestCase):
    def test_saved_keys_become_identities_without_retaining_unused_numbers(self):
        decoded = fixture()
        net = decoded.board.one('Nets/Net')
        traces = net.add('Traces')
        first = trace(traces, 19, (0, 41, 5, 999), (-1, 123, 456, 789))
        second = trace(traces, 32, (1, 73, 19, 1), (0, 41, 12, -1))
        decoded.upgrades = SimpleNamespace(nets=(SimpleNamespace(net=net, traces=(first, second)),), separate_traces=())
        result = assemble_routing(decoded)
        document = result.document
        self.assertIs(second.trace['Target1'], first.trace.one('Points/Point[2]'))
        self.assertEqual((second.trace['Object1'], second.trace['SubObject1'], second.trace['Point1']), (0, 0, 1))
        self.assertEqual(first.trace['Point1'], -1)
        self.assertEqual((first.trace['Object2'], first.trace['SubObject2'], first.trace['Point2']), (-1, -1, -1))
        for node in (first.trace, second.trace):
            self.assertIsNone(node.child('Object1'))
            self.assertIsNone(node.child('Connected1'))
        second.trace.move_to(traces, 0)
        self.assertEqual(second.trace['SubObject1'], 1)
        self.assertIs(first.trace['Target1'], result.core.pads[41, 5])
        self.assertFalse(document.complete)

    def test_pair_segment_and_separate_trace_codes_bind_their_actual_targets(self):
        decoded = fixture()
        board = decoded.board
        positive = board.one('Nets/Net')
        negative = board.one('Nets').add('Net')
        for name, value in (('Number', 98), ('Enabled', True), ('Name', 'Negative')):
            negative.add(name, value)
        negative.add('Pads')
        negative.add('Traces')
        normal = trace(positive.add('Traces'), 19, (6, 123, 61, 1), (5, 0, 1, 0))
        pair = board.add('DifferentialPairs').add('DifferentialPair', 0)
        for name, value in (('Number', 7), ('Enabled', True), ('Name', 'Pair'), ('PosNet', 73), ('NegNet', 98)):
            pair.add(name, value)
        segment = pair.add('Segments').add('Segment', 0)
        centers = segment.add('CenterPoints')
        centers.add('CenterPoint', 0)
        center = centers.add('CenterPoint', 1)
        center.add('X', 0)
        center.add('Y', 0)
        point = center.add('PosPoints').add('PosPoint', 0)
        point.add('X', 0)
        point.add('Y', 0)
        separate = trace(pair.add('PosSeparateTraces'), 61, (0, 41, 5, -1), (-1, 0, 0, 0), 'PosTrace')
        pair.add('NegSeparateTraces')
        decoded.upgrades = SimpleNamespace(nets=(SimpleNamespace(net=positive, traces=(normal,)),
            SimpleNamespace(net=negative, traces=())), separate_traces=(separate,))
        result = assemble_routing(decoded)
        self.assertIs(pair['PosNet'], positive)
        self.assertIs(pair['NegNet'], negative)
        self.assertIs(normal.trace['Target1'], separate.trace.one('Points/Point[2]'))
        self.assertEqual((normal.trace['Object1'], normal.trace['SubObject1'], normal.trace['Point1']), (-1, 0, 1))
        self.assertEqual(normal.trace['Connected1'], 'Separate Trace')
        self.assertIs(normal.trace['Target2'], point)
        self.assertEqual((normal.trace['Object2'], normal.trace['SubObject2'], normal.trace['Point2']), (0, 1, 0))
        self.assertEqual(normal.trace['Connected2'], 'Segment')
        self.assertNotIn('Number', pair)
        self.assertEqual(pair['PosNetIndex'], 0)
        self.assertEqual(len(result.separate_traces), 1)


if __name__ == '__main__':
    unittest.main()
