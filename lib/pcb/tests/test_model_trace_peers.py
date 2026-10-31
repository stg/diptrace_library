"""One peer relationship supplies both ordinary and separate trace views."""
import unittest

from lib.common.model import Element
from lib.common.references import Property, ReferenceError
from lib.pcb.model import routing_records
from lib.pcb.model.objects import new_trace
from lib.pcb.formats.routing_projection import peer_backlink
from lib.pcb.tests.test_model_pair_pads import design as pair_design


def separate(pair):
    trace = pair.one('PosSeparateTraces').append(Element('PosTrace').bind_schema(routing_records.SEPARATE_TRACE))
    trace.add('Points').bind_schema(routing_records.COLLECTIONS['Points'])
    return trace


def design():
    document, pair, *_ = pair_design()
    ordinary = pair['PosNet'].one('Traces').append(new_trace())
    other = ordinary.parent.append(new_trace())
    peer = separate(pair)
    peer['NetTrace'] = ordinary
    return document, pair, ordinary, other, peer


class TracePeerModelTests(unittest.TestCase):
    def test_peer_identity_and_index_projections_follow_both_trace_orders(self):
        document, pair, ordinary, _, peer = design()
        probe = document.root.add('Probe', -1, -1)
        document.references.bind(probe, ordinary, Property(probe, 'PairSeparateTrace', argument=0), role='ordinary-probe')
        document.references.bind(probe, peer, Property(probe, 'TraceId', argument=1), role='separate-probe')
        self.assertEqual(probe.values, (0, 0))
        separate(pair)
        peer.move_to(peer.parent)
        ordinary.move_to(ordinary.parent)
        self.assertEqual(probe.values, (1, 1))
        self.assertIs(ordinary['SeparateTrace'], peer)
        self.assertIs(peer['NetTrace'], ordinary)
        document.validate()

    def test_retarget_and_disconnect_update_the_inverse_without_a_second_link(self):
        document, _, ordinary, other, peer = design()
        peer['NetTrace'] = other
        self.assertIsNone(ordinary['SeparateTrace'])
        self.assertEqual(ordinary['PairSeparateTrace'], -1)
        self.assertIs(other['SeparateTrace'], peer)
        peer['NetTrace'] = None
        self.assertIsNone(other['SeparateTrace'])
        self.assertEqual(peer['TraceId'], -1)
        document.validate()

    def test_an_ordinary_trace_has_at_most_one_peer_and_failed_edits_are_atomic(self):
        document, pair, ordinary, other, peer = design()
        second = separate(pair)
        with self.assertRaisesRegex(ReferenceError, 'already has'):
            second['NetTrace'] = ordinary
        self.assertIsNone(second['NetTrace'])
        second['NetTrace'] = other
        with self.assertRaisesRegex(ReferenceError, 'already has'):
            peer['NetTrace'] = other
        self.assertIs(peer['NetTrace'], ordinary)
        self.assertIs(other['SeparateTrace'], second)
        document.validate()

    def test_wrong_net_and_foreign_targets_are_rejected(self):
        document, pair, ordinary, _, peer = design()
        negative = pair['NegNet'].one('Traces').append(new_trace())
        with self.assertRaisesRegex(ReferenceError, 'corresponding pair net'):
            peer['NetTrace'] = negative
        foreign, _, other, *_ = design()
        with self.assertRaises(ReferenceError):
            peer['NetTrace'] = other
        self.assertIs(peer['NetTrace'], ordinary)
        document.validate()
        foreign.validate()

    def test_pair_net_changes_and_target_moves_keep_the_peer_scope_coherent(self):
        document, pair, ordinary, _, peer = design()
        pair.one('PadPoints/PadPoint')['PosPad'] = None
        negative = pair['NegNet']
        with self.assertRaisesRegex(ReferenceError, 'corresponding pair net'):
            pair['PosNet'] = negative
        with self.assertRaisesRegex(ReferenceError, 'corresponding pair net'):
            ordinary.move_to(negative.one('Traces'))
        self.assertIs(peer['NetTrace'], ordinary)
        self.assertIs(ordinary.parent.parent, pair['PosNet'])
        document.validate()

    def test_segment_ownership_suppresses_only_the_export_compatibility_cache(self):
        document, pair, ordinary, _, peer = design()
        probe = document.root.add('Probe', -1)
        document.references.bind(probe, ordinary, Property(probe, 'PairSeparateTrace', argument=0), role='probe')
        self.assertEqual(probe.values, (0,))
        self.assertEqual(peer_backlink(ordinary), 0)
        segment = pair.one('Segments').append(Element('Segment').bind_schema(routing_records.SEGMENT))
        segment.add('CenterPoints').bind_schema(routing_records.COLLECTIONS['CenterPoints'])
        segment['PosTrace'] = ordinary
        self.assertEqual(probe.values, (0,))
        self.assertEqual(peer_backlink(ordinary), -1)
        self.assertIs(ordinary['SeparateTrace'], peer)
        self.assertIs(peer['NetTrace'], ordinary)
        segment['PosTrace'] = None
        self.assertEqual(probe.values, (0,))
        self.assertEqual(peer_backlink(ordinary), 0)
        document.validate()

    def test_clone_and_removal_keep_the_single_relationship_resolved(self):
        document, _, ordinary, _, peer = design()
        with self.assertRaises(ReferenceError):
            document.remove(ordinary)
        copied = document.clone()
        other_peer = copied.one('/Board/DifferentialPairs/DifferentialPair/PosSeparateTraces/PosTrace')
        self.assertIsNot(other_peer['NetTrace'], ordinary)
        self.assertIs(other_peer['NetTrace']['SeparateTrace'], other_peer)
        other_peer['NetTrace'] = None
        self.assertIs(ordinary['SeparateTrace'], peer)
        copied.validate()
        document.validate()


if __name__ == '__main__':
    unittest.main()
