"""Pair geometry memberships remain identities; connection counters are output."""
import unittest

from lib.common.model import Element
from lib.common.references import Property, ReferenceError
from lib.pcb.model import routing_records
from lib.pcb.model.objects import new_point, new_trace
from lib.pcb.formats.routing_projection import point_memberships
from lib.pcb.tests.test_model_pair_ranges import design as range_design, segment, center


def side_point(row, side='Pos'):
    collection = row.child(side+'Points')
    if collection is None:
        collection = row.add(side+'Points').bind_schema(routing_records.COLLECTIONS[side+'Points'])
    point = collection.append(Element(side+'Point').bind_schema(routing_records.SIDE_POINT))
    point['X'], point['Y'] = 1, 2
    return point


def design():
    document, pair, seg, row, trace, points = range_design()
    target = side_point(row)
    points[0]['PairTarget'], points[1]['PairTarget'] = target, row
    return document, pair, seg, row, trace, points, target


class PairMembershipModelTests(unittest.TestCase):
    def test_live_indices_follow_side_and_center_order_and_owner_changes(self):
        document, _, seg, row, _, points, target = design()
        probe = document.root.add('Probe', -1, -1)
        document.references.bind(probe, points[0], Property(probe, 'PairPoint', argument=0),
                                 Property(probe, 'PairSubPoint', argument=1), role='probe')
        self.assertEqual(probe.values, (0, 0))
        other = center(seg)
        other.add('PosPoints').bind_schema(routing_records.COLLECTIONS['PosPoints'])
        target.move_to(other.one('PosPoints'))
        self.assertEqual(probe.values, (1, 0))
        side_point(other)
        target.move_to(target.parent)
        self.assertEqual(probe.values, (1, 1))
        other.move_to(other.parent, 0)
        self.assertEqual(probe.values, (0, 1))
        self.assertIs(points[0]['PairTarget'], target)
        self.assertIs(points[1]['PairTarget'], row)
        document.validate()

    def test_membership_checks_the_segment_trace_and_side(self):
        document, _, seg, row, trace, points, target = design()
        negative = side_point(row, 'Neg')
        with self.assertRaisesRegex(ReferenceError, 'segment trace and pair side'):
            points[0]['PairTarget'] = negative
        self.assertIs(points[0]['PairTarget'], target)
        with self.assertRaises(ReferenceError):
            points[0]['PairTarget'] = trace
        other_trace = trace.parent.append(new_trace())
        foreign_center = center(segment(seg.parent.parent, other_trace))
        with self.assertRaisesRegex(ReferenceError, 'segment trace and pair side'):
            points[0]['PairTarget'] = foreign_center
        document.validate()

    def test_segment_trace_retarget_and_reference_removal_preflight_members(self):
        document, _, seg, row, trace, points, _ = design()
        row['PosStartPoint'], row['PosEndPoint'] = None, None
        other = trace.parent.append(new_trace())
        with self.assertRaisesRegex(ReferenceError, 'point membership'):
            seg['PosTrace'] = other
        with self.assertRaisesRegex(ReferenceError, 'point membership'):
            seg['PosTrace'] = None
        self.assertIs(seg['PosTrace'], trace)
        for point in points:
            point['PairTarget'] = None
        seg['PosTrace'] = other
        document.validate()

    def test_point_and_target_moves_cannot_leave_another_segment_scope(self):
        document, _, seg, row, trace, points, target = design()
        row['PosStartPoint'], row['PosEndPoint'] = None, None
        other_trace = trace.parent.append(new_trace())
        other_center = center(segment(seg.parent.parent, other_trace))
        other_center.add('PosPoints').bind_schema(routing_records.COLLECTIONS['PosPoints'])
        with self.assertRaisesRegex(ReferenceError, 'point membership'):
            points[0].move_to(other_trace.one('Points'))
        with self.assertRaisesRegex(ReferenceError, 'point membership'):
            target.move_to(other_center.one('PosPoints'))
        self.assertIs(points[0].parent, trace.one('Points'))
        self.assertIs(target.parent, row.one('PosPoints'))
        document.validate()

    def test_connection_type_changes_reject_incompatible_side_associations(self):
        document, _, _, row, _, points, target = design()
        with self.assertRaisesRegex(ReferenceError, 'connection membership'):
            row['Type'] = 2
        self.assertEqual(row.get('Type', 0), 0)
        points[0]['PairTarget'] = row
        row['Type'] = 2
        with self.assertRaisesRegex(ReferenceError, 'connection membership'):
            points[0]['PairTarget'] = target
        self.assertIs(points[0]['PairTarget'], row)
        document.validate()

    def test_connection_run_projection_is_single_pass_and_does_not_change_the_model(self):
        document, _, seg, row, trace, points, _ = design()
        for point in points:
            point['PairTarget'] = None
        row['Type'] = 2
        other, ordinary = center(seg), center(seg)
        other['Type'] = 2
        points += [trace.one('Points').append(new_point()) for _ in range(2)]
        for point, target in zip(points, (row, row, other, ordinary, row)):
            point['PairTarget'] = target
        self.assertEqual(list(point_memberships(trace)), [(0, 1), (0, 2), (1, 3), (2, -1), (0, 1)])
        self.assertEqual([point['PairSubPoint'] for point in points], [-1]*5)
        self.assertTrue(all(point.child('PairSubPoint') is None for point in points))
        document.validate()

    def test_removal_disconnection_and_cloning_preserve_identity(self):
        document, _, _, _, _, points, target = design()
        with self.assertRaises(ReferenceError):
            document.remove(target)
        copied = document.clone()
        point = copied.one('/Board/Nets/Net[1]/Traces/Trace/Points/Point[1]')
        self.assertIsNot(point['PairTarget'], target)
        self.assertIs(point['PairTarget']._owner(), copied)
        point['PairTarget'] = None
        self.assertIs(points[0]['PairTarget'], target)
        points[0]['PairTarget'] = None
        self.assertEqual((points[0]['PairPoint'], points[0]['PairSubPoint']), (-1, -1))
        document.remove(target)
        copied.validate()
        document.validate()


if __name__ == '__main__':
    unittest.main()
