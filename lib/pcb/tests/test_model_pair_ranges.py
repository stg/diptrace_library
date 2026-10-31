"""Differential center ranges follow trace/point identities during data edits."""
import unittest

from lib.common.model import Element
from lib.common.references import Property, ReferenceError
from lib.pcb.model import routing_records
from lib.pcb.model.objects import new_point, new_trace
from lib.pcb.tests.test_model_pair_pads import design as pad_design


def segment(pair, trace):
    node = pair.one('Segments').append(Element('Segment').bind_schema(routing_records.SEGMENT))
    node['PosTrace'] = trace
    node.add('CenterPoints').bind_schema(routing_records.COLLECTIONS['CenterPoints'])
    return node


def center(segment):
    node = segment.one('CenterPoints').append(Element('CenterPoint').bind_schema(routing_records.CENTER))
    node['X'], node['Y'] = 1, 2
    return node


def design():
    document, pair, *_ = pad_design()
    net = pair['PosNet']
    trace = net.one('Traces').append(new_trace())
    points = [trace.one('Points').append(new_point(x=i)) for i in range(3)]
    seg = segment(pair, trace)
    row = center(seg)
    # Wrapped/reversed ranges are permitted. This records current design data;
    # these relationships do not calculate a path between the chosen points.
    row['PosStartPoint'], row['PosEndPoint'] = points[2], points[0]
    return document, pair, seg, row, trace, points


class PairRangeModelTests(unittest.TestCase):
    def test_range_projections_follow_reordering_without_changing_geometry(self):
        document, pair, seg, row, trace, points = design()
        probe = document.root.add('Probe', -1, -1)
        document.references.bind(probe, row,
            Property(probe, 'PosTrace_StartPoint', argument=0),
            Property(probe, 'PosTrace_EndPoint', argument=1), role='probe')
        trace_probe = document.root.add('TraceProbe', -1)
        document.references.bind(trace_probe, seg, Property(trace_probe, 'PosTraceIndex', argument=0), role='probe')
        self.assertEqual(probe.values, (2, 0))
        points[2].move_to(points[2].parent, 0)
        trace.parent.append(new_trace())
        trace.move_to(trace.parent)
        self.assertEqual(probe.values, (0, 1))
        self.assertEqual(trace_probe.values, (1,))
        self.assertIs(row['PosStartPoint'], points[2])
        self.assertEqual((row['X'], row['Y']), (1, 2))
        self.assertEqual([point['X'] for point in trace.one('Points').children()], [2, 0, 1])
        document.validate()

    def test_range_targets_must_belong_to_the_segment_trace(self):
        document, pair, seg, row, trace, points = design()
        other = trace.parent.append(new_trace())
        point = other.one('Points').append(new_point())
        with self.assertRaisesRegex(ReferenceError, 'segment trace'):
            row['PosStartPoint'] = point
        self.assertIs(row['PosStartPoint'], points[2])
        with self.assertRaisesRegex(ReferenceError, 'segment trace'):
            seg['PosTrace'] = other
        self.assertIs(seg['PosTrace'], trace)
        row['PosStartPoint'], row['PosEndPoint'] = None, None
        seg['PosTrace'] = other
        row['PosStartPoint'] = point
        self.assertIs(row['PosStartPoint'], point)
        self.assertEqual(row['PosTrace_EndPoint'], -1)
        document.validate()

    def test_pair_net_changes_and_trace_moves_reject_attached_range_contradictions(self):
        document, pair, seg, row, trace, points = design()
        negative = pair['NegNet']
        # Disconnect the independent paired-pad row to isolate segment rules.
        pair.one('PadPoints/PadPoint')['PosPad'] = None
        with self.assertRaisesRegex(ReferenceError, 'corresponding pair net'):
            pair['PosNet'] = negative
        with self.assertRaisesRegex(ReferenceError, 'corresponding pair net'):
            trace.move_to(negative.one('Traces'))
        self.assertIs(seg['PosTrace'], trace)
        self.assertIs(trace.parent.parent, pair['PosNet'])
        document.validate()

    def test_moving_a_center_cannot_leave_ranges_in_another_segment_trace(self):
        document, pair, seg, row, trace, points = design()
        other_trace = trace.parent.append(new_trace())
        other = segment(pair, other_trace)
        with self.assertRaisesRegex(ReferenceError, 'segment trace'):
            row.move_to(other.one('CenterPoints'))
        self.assertIs(row.parent, seg.one('CenterPoints'))
        with self.assertRaises(ReferenceError):
            row.move_to(document.root.add('Other'))
        self.assertIs(row.parent, seg.one('CenterPoints'))
        document.validate()

    def test_removal_and_clone_keep_resolved_range_identity(self):
        document, pair, seg, row, trace, points = design()
        with self.assertRaises(ReferenceError):
            document.remove(points[2])
        with self.assertRaisesRegex(ReferenceError, 'segment trace'):
            seg['PosTrace'] = None
        copied = document.clone()
        copied_row = copied.one('/Board/DifferentialPairs/DifferentialPair/Segments/Segment/CenterPoints/CenterPoint')
        self.assertIsNot(copied_row['PosStartPoint'], points[2])
        self.assertIs(copied_row['PosStartPoint']._owner(), copied)
        copied_row['PosStartPoint'] = None
        self.assertIs(row['PosStartPoint'], points[2])
        copied.validate()
        document.validate()


if __name__ == '__main__':
    unittest.main()
