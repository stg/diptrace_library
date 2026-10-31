"""Routing references survive data edits without routing new geometry."""
import unittest
from unittest.mock import patch

from lib.common.model import Element
from lib.common.references import Property, ReferenceError
from lib.pcb.model.objects import new_document, new_component, new_pad, new_net, new_trace, new_point, new_pair
from lib.pcb.model import routing_records


class RoutingTests(unittest.TestCase):
    def design(self):
        document = new_document()
        board = document.one('/Board')
        component = board.one('Components').append(new_component('Device', 'U1'))
        pad = component.one('Pattern/Pads').append(new_pad('1'))
        net = board.one('Nets').append(new_net('Signal'))
        other = board.one('Nets').append(new_net('Other'))
        pad['Net'] = net
        trace = net.one('Traces').append(new_trace())
        points = trace.one('Points')
        first, second = points.append(new_point(x=1)), points.append(new_point(x=2))
        return document, component, pad, net, other, trace, first, second

    def probe(self, document, trace, end):
        probe = document.root.add('Probe', -1, -1, -1)
        document.references.bind(probe, trace,
            *(Property(probe, name+str(end), argument=index)
              for index, name in enumerate(('Object', 'SubObject', 'Point'))), role='probe')
        return probe

    def pair(self, document, positive, negative):
        collection = document.one('/Board').add('DifferentialPairs').bind_schema(
            routing_records.COLLECTIONS['DifferentialPairs'])
        pair = collection.append(new_pair('Pair'))
        pair['PosNet'], pair['NegNet'] = positive, negative
        segment = pair.one('Segments').add('Segment').bind_schema(routing_records.SEGMENT)
        centers = segment.add('CenterPoints').bind_schema(routing_records.COLLECTIONS['CenterPoints'])
        center = centers.add('CenterPoint').bind_schema(routing_records.CENTER)
        center.add('X', 1)
        center.add('Y', 2)
        positive_points = center.add('PosPoints').bind_schema(routing_records.COLLECTIONS['PosPoints'])
        center.add('NegPoints').bind_schema(routing_records.COLLECTIONS['NegPoints'])
        point = positive_points.add('PosPoint').bind_schema(routing_records.SIDE_POINT)
        point.add('X', 3)
        point.add('Y', 4)
        separate = pair.one('PosSeparateTraces').add('PosTrace').bind_schema(routing_records.SEPARATE_TRACE)
        separate.add('Points').bind_schema(routing_records.COLLECTIONS['Points'])
        separate.one('Points').append(new_point())
        return pair, segment, center, point, separate

    def test_pad_endpoint_has_one_identity_and_calculated_public_indices(self):
        document, _, pad, _, _, trace, _, _ = self.design()
        self.assertIsNone(trace['Target1'])
        self.assertEqual(trace['Connected1'], 'Free')
        trace['Target1'] = pad
        self.assertEqual((trace['Connected1'], trace['Object1'], trace['SubObject1'], trace['Point1']),
                         ('Pad', 0, 1, -1))
        self.assertIsNone(trace.child('Object1'))
        with self.assertRaises(TypeError):
            trace['Object1'] = 1
        document.validate()

    def test_reorder_and_retarget_update_consumers_without_global_scans(self):
        document, component, pad, net, other, trace, first, second = self.design()
        trace['Target1'] = pad
        copied = self.probe(document, trace, 1)
        extra = component.parent.append(new_component('Another', 'U2'))
        another_pad = component.one('Pattern/Pads').append(new_pad('2'))
        other_trace = net.one('Traces').append(new_trace())
        point = other_trace.one('Points').append(new_point())
        with patch.object(document.root, 'walk', side_effect=AssertionError('whole document scan')), \
             patch.object(type(document.references), '__iter__', side_effect=AssertionError('whole graph scan')):
            component.move_to(component.parent, 1)
            another_pad.move_to(another_pad.parent, 0)
            self.assertEqual(copied.values, (1, 2, -1))
            trace['Target1'] = point
            self.assertEqual(trace['Connected1'], 'Trace')
            self.assertEqual(copied.values, (0, 1, 0))
            other.move_to(other.parent, 0)
            other_trace.move_to(other_trace.parent, 0)
            self.assertEqual(copied.values, (1, 0, 0))
            point.move_to(trace.one('Points'), 1)
            self.assertEqual(copied.values, (1, 1, 1))
        self.assertIs(trace['Target1'], point)
        self.assertEqual(first['X'], 1)
        self.assertEqual(second['X'], 2)
        self.assertEqual(extra['RefDes'], 'U2')
        document.validate()

    def test_membership_edits_cannot_disconnect_a_routed_pad(self):
        document, _, pad, net, other, trace, _, _ = self.design()
        trace['Target1'] = pad
        member = net.one('Pads/Item')
        for target in (None, other):
            with self.assertRaisesRegex(ReferenceError, 'attached trace'):
                pad['Net'] = target
        with self.assertRaisesRegex(ReferenceError, 'attached trace'):
            member.move_to(other.one('Pads'))
        with self.assertRaisesRegex(ReferenceError, 'attached trace'):
            document.remove(member)
        self.assertIs(pad['Net'], net)
        self.assertIs(member.parent, net.one('Pads'))
        trace['Target1'] = None
        pad['Net'] = other
        document.validate()

    def test_trace_and_target_moves_reject_cross_net_attachments_atomically(self):
        document, _, pad, net, other, trace, _, _ = self.design()
        target_trace = net.one('Traces').append(new_trace())
        target = target_trace.one('Points').append(new_point())
        trace['Target1'], trace['Target2'] = pad, target
        for record in (trace, target_trace):
            with self.assertRaisesRegex(ReferenceError, 'same net'):
                record.move_to(other.one('Traces'))
            self.assertIs(record.parent, net.one('Traces'))
        foreign = new_document().one('/Board/Nets').append(new_net()).one('Traces').append(new_trace())
        foreign_point = foreign.one('Points').append(new_point())
        with self.assertRaises(ReferenceError):
            trace['Target1'] = foreign_point
        self.assertIs(trace['Target1'], pad)
        document.validate()

    def test_referenced_points_are_protected_until_the_endpoint_is_disconnected(self):
        document, _, _, net, _, trace, first, _ = self.design()
        other = net.one('Traces').append(new_trace())
        other['Target2'] = first
        with self.assertRaises(ReferenceError):
            document.remove(first)
        other['Target2'] = None
        document.remove(first)
        self.assertEqual(other['Connected2'], 'Free')
        self.assertEqual((other['Object2'], other['SubObject2'], other['Point2']), (-1, -1, -1))
        self.assertIs(trace.parent, net.one('Traces'))
        document.validate()

    def test_pair_segment_and_separate_trace_targets_are_distinct(self):
        document, _, _, positive, negative, trace, _, _ = self.design()
        pair, segment, center, side_point, separate = self.pair(document, positive, negative)
        trace['Target1'] = side_point
        separate['Target1'] = side_point
        trace['Target2'] = separate.one('Points/Point')
        self.assertEqual((trace['Connected1'], trace['Object1'], trace['SubObject1'], trace['Point1']),
                         ('Segment', 0, 0, 0))
        self.assertEqual((trace['Connected2'], trace['Object2'], trace['SubObject2'], trace['Point2']),
                         ('Separate Trace', -1, 0, 0))
        copied = self.probe(document, trace, 1)
        extra = side_point.parent.add('PosPoint').bind_schema(routing_records.SIDE_POINT)
        extra.add('X', 5)
        extra.add('Y', 6)
        extra.move_to(extra.parent, 0)
        self.assertEqual(copied.values, (0, 0, 1))
        with self.assertRaisesRegex(ReferenceError, 'same net'):
            pair['PosNet'] = negative
        with self.assertRaises(ReferenceError):
            pair['PosNet'] = None
        self.assertIs(pair['PosNet'], positive)
        self.assertIs(segment.parent, pair.one('Segments'))
        self.assertIs(center.parent, segment.one('CenterPoints'))
        document.validate()

    def test_clone_remaps_endpoint_and_pair_identities(self):
        document, _, pad, positive, negative, trace, _, _ = self.design()
        pair, _, _, point, _ = self.pair(document, positive, negative)
        trace['Target1'], trace['Target2'] = pad, point
        copy = document.clone()
        clone_trace = copy.one('/Board/Nets/Net[1]/Traces/Trace')
        self.assertIs(clone_trace['Target1'], copy.one('/Board/Components/Component/Pattern/Pads/Pad'))
        self.assertIs(clone_trace['Target2'], copy.one(
            '/Board/DifferentialPairs/DifferentialPair/Segments/Segment/CenterPoints/CenterPoint/PosPoints/PosPoint'))
        self.assertIsNot(clone_trace['Target2'], point)
        copy.one('/Board/DifferentialPairs/DifferentialPair')['Name'] = 'Changed'
        self.assertEqual(pair['Name'], 'Pair')
        copy.validate()
        document.validate()

    def test_endpoint_type_consumers_follow_point_ownership_changes(self):
        document, _, _, positive, negative, trace, _, _ = self.design()
        _, _, _, _, separate = self.pair(document, positive, negative)
        target = separate.one('Points/Point')
        trace['Target1'] = target
        probe = document.root.add('KindProbe', '')
        document.references.bind(probe, trace, Property(probe, 'Connected1'), role='kind-probe')
        self.assertEqual(probe.values, ('Separate Trace',))
        target.move_to(trace.one('Points'))
        self.assertEqual(trace['Connected1'], 'Trace')
        self.assertEqual(probe.values, ('Trace',))
        document.validate()

    def test_low_level_assignment_and_disabled_owner_guards_are_atomic(self):
        document, _, pad, net, other, trace, _, _ = self.design()
        trace['Target1'] = pad
        member = net.one('Pads/Item')
        assignment = document.references.outgoing(member, role='net-member')[0]
        with self.assertRaisesRegex(ReferenceError, 'attached trace'):
            document.references.discard(assignment)
        self.assertIs(member['Pad'], pad)
        other['Enabled'] = False
        proposal = new_trace()
        with self.assertRaisesRegex(ReferenceError, 'enabled net'):
            other.one('Traces').append(proposal)
        self.assertIsNone(proposal.parent)
        document.validate()

    def test_shared_center_endpoint_selects_its_side_from_the_trace_net(self):
        document, _, _, positive, negative, trace, _, _ = self.design()
        _, _, center, _, _ = self.pair(document, positive, negative)
        trace['Target1'] = center
        other = negative.one('Traces').append(new_trace())
        other['Target1'] = center
        self.assertEqual((trace['Connected1'], trace['Point1']), ('Segment', -1))
        document.validate()


if __name__ == '__main__':
    unittest.main()
