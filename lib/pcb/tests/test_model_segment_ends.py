"""Differential segment ends identify paired pads or centers, never saved indices."""
import unittest

from lib.common.model import Element
from lib.common.references import Property, ReferenceError
from lib.pcb.model import routing_records
from lib.pcb.model.objects import new_pair
from lib.pcb.tests.test_model_pair_pads import design as pair_design


def segment(pair):
    node = pair.one('Segments').append(Element('Segment').bind_schema(routing_records.SEGMENT))
    points = node.add('CenterPoints').bind_schema(routing_records.COLLECTIONS['CenterPoints'])
    for i in range(2):
        point = points.append(Element('CenterPoint').bind_schema(routing_records.CENTER))
        point['X'], point['Y'] = i+10, i+20
    return node


def design():
    document, pair, row, *_ = pair_design()
    first, second = segment(pair), segment(pair)
    center = second.one('CenterPoints/CenterPoint[2]')
    first['Start'], first['End'] = row, center
    return document, pair, first, second, row, center


class SegmentEndModelTests(unittest.TestCase):
    def test_both_endpoint_kinds_follow_target_and_owner_order(self):
        document, pair, first, second, row, center = design()
        probe = document.root.add('Probe', -1, -1, -1)
        document.references.bind(probe, first,
            *(Property(probe, name, argument=i) for i, name in
              enumerate(('StartPoint', 'EndPoint', 'EndSegment'))), role='probe')
        self.assertEqual(probe.values, (0, 1, 1))
        pair.one('PadPoints').append(Element('PadPoint').bind_schema(routing_records.PAIRED_PAD))
        row.move_to(row.parent)
        center.move_to(center.parent, 0)
        second.move_to(second.parent, 0)
        self.assertEqual(probe.values, (1, 0, 0))
        self.assertEqual(first['StartSegment'], -1)
        self.assertIs(first['Start'], row)
        self.assertIs(first['End'], center)
        self.assertEqual((center['X'], center['Y']), (11, 21))
        document.validate()

    def test_center_owner_changes_within_the_pair_keep_the_endpoint_identity(self):
        document, _, first, _, _, center = design()
        center.move_to(first.one('CenterPoints'), 0)
        self.assertIs(first['End'], center)
        self.assertEqual((first['EndSegment'], first['EndPoint']), (0, 0))
        document.validate()

    def test_incompatible_targets_fail_atomically(self):
        document, pair, first, _, row, _ = design()
        other = pair.parent.append(new_pair('Other'))
        other['PosNet'], other['NegNet'] = pair['PosNet'], pair['NegNet']
        foreign_center = segment(other).one('CenterPoints/CenterPoint[1]')
        for target in (foreign_center, row['PosPad'], document.root):
            with self.subTest(kind=target.kind), self.assertRaisesRegex(ReferenceError, 'same pair'):
                first['Start'] = target
            self.assertIs(first['Start'], row)
        document.validate()

    def test_source_and_target_moves_cannot_cross_pair_scope(self):
        document, pair, first, _, row, _ = design()
        other = pair.parent.append(new_pair('Other'))
        other['PosNet'], other['NegNet'] = pair['PosNet'], pair['NegNet']
        with self.assertRaisesRegex(ReferenceError, 'same pair'):
            first.move_to(other.one('Segments'))
        self.assertIs(first.parent, pair.one('Segments'))
        with self.assertRaisesRegex(ReferenceError, 'same pair'):
            row.move_to(other.one('PadPoints'))
        self.assertIs(row.parent, pair.one('PadPoints'))
        document.validate()

    def test_disconnection_and_removal_have_no_stale_numeric_selectors(self):
        document, _, first, _, row, center = design()
        with self.assertRaises(ReferenceError):
            document.remove(row)
        with self.assertRaises(ReferenceError):
            document.remove(center)
        first['Start'], first['End'] = None, None
        self.assertEqual((first['StartPoint'], first['StartSegment'], first['EndPoint'], first['EndSegment']),
                         (-1, -1, -1, -1))
        document.remove(row)
        document.remove(center)
        document.validate()

    def test_clone_remaps_both_endpoint_identities(self):
        document, _, first, _, row, center = design()
        copied = document.clone()
        other = copied.one('/Board/DifferentialPairs/DifferentialPair/Segments/Segment[1]')
        self.assertIsNot(other['Start'], row)
        self.assertIsNot(other['End'], center)
        self.assertIs(other['Start']._owner(), copied)
        self.assertIs(other['End']._owner(), copied)
        other['End'] = None
        self.assertIs(first['End'], center)
        copied.validate()
        document.validate()


if __name__ == '__main__':
    unittest.main()
