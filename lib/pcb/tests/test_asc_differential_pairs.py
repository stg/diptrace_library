"""Differential ASC dialects bind to editable pad and route identities."""
from decimal import Decimal
import unittest

from lib.common.asc import loads, dumps
from lib.common.references import ReferenceError
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.assembly.routing import assemble_routing
from lib.pcb.formats.errors import PcbError
from lib.pcb.formats.routing_projection import peer_backlink
from lib.pcb.model.objects import new_component
from lib.pcb.tests.test_asc_core import fixture
from lib.pcb.tests.test_asc_routing import TRACE, SEPARATE_TRACE


PAIR = '''(DifferentialPair "Y"
  (Enabled "Y") (Number 7) (PosNet 73) (NegNet 98) (NetClass -1)
  (CustomColor "N") (TraceColor 42) (PadPoints_Auto "Y") (RouteMode 3)
  (PadPoints 1 (pt 17 9 17 11))
  (Segments (Segment (PosLine 53) (NegLine -1)
    (StartPoint 0) (EndPoint 0) (StartSegment -1) (EndSegment -1)
    (CenterPoints (CenterPoint (X 10) (Y 20) (Layer 0) (ViaStyle -1)
      (Orientation 1) (Type 0) (PosLine_StartPoint 0) (PosLine_EndPoint 1)
      (NegLine_StartPoint -1) (NegLine_EndPoint -1) (PosLineSide 0)
      (Necked "N") (Selected "Y") (PhaseError "N")
      (PosPoints 1 (pt 1.25 2.5 "Y" 0 -1 "N" 2 0.37 "Y"))
      (NegPoints 1 (pt -1.25 -2.5 "N" 0 -1 "Y" 0 0 "N"))
    ))))
  (SeparateLines_Pos) (SeparateLines_Neg))'''


def design(*, routes=True):
    source = loads(fixture())
    board = source.one('/Board')
    positive = board.one('Nets/Net')
    negative = positive.clone()
    negative.set_values('Negative')
    negative.one('Number').set_values(98)
    negative.one('Component/pt[1]').detach()
    positive.one('Component/pt[2]').detach()
    negative.move_to(positive.parent)
    board.one('Components/Component/Pads/Pad[3]/NetNumber').set_values(98)
    pair = loads(PAIR).one('/DifferentialPair')
    pair.move_to(board.add('DifferentialPairs'))
    if routes:
        ordinary = loads(TRACE).one('/Line')
        ordinary.one('ConnectMode1').set_values(6)
        ordinary.one('ConnectL1').set_values(61)
        ordinary.one('ConnectP1').set_values(0)
        ordinary.one('ConnectP2').set_values(9)
        ordinary.move_to(positive.one('Lines'))
        for side, pad in (('Pos', 9), ('Neg', 11)):
            trace = loads(SEPARATE_TRACE).one('/Line_Pos')
            trace.kind = 'Line_'+side
            for name, value in dict(Connect1=0, ConnectL1=0, ConnectP1=0, ConnectMode1=5,
                                    ConnectL2=pad, NetLine_Link=53 if side == 'Pos' else -1,
                                    OldNumber=61 if side == 'Pos' else 62).items():
                trace.one(name).set_values(value)
            trace.move_to(pair.one('SeparateLines_'+side))
    else:
        pair.one('Segments/Segment/PosLine').set_values(-1)
        for end in ('Start', 'End'):
            pair.one('Segments/Segment/CenterPoints/CenterPoint/PosLine_'+end+'Point').set_values(-1)
    return dumps(source, preserve=False)


class AscDifferentialPairTests(unittest.TestCase):
    def test_each_compact_dialect_expands_named_current_geometry(self):
        data = prepare_core(design())
        pair = data.board.one('DifferentialPairs/DifferentialPair')
        self.assertEqual((pair['Name'], pair['AutoPadPoints'], pair['TraceColor']), ('Y', True, 42))
        center = pair.one('Segments/Segment/CenterPoints/CenterPoint')
        self.assertEqual(center['Lay'], 0)
        self.assertIsNone(center.child('Layer'))
        self.assertEqual(center['PosTrace_EndPoint'], 1)
        point = center.one('PosPoints/PosPoint')
        self.assertEqual((point['X'], point['Y']), (Decimal('1.25'), Decimal('2.5')))
        self.assertEqual((point['Selected'], point['Necked'], point['Arc']), (True, False, True))
        self.assertEqual((point['Meander'], point['MeanderAngle']), (2, Decimal('.37')))
        self.assertEqual(center.one('NegPoints/NegPoint')['Necked'], True)
        self.assertEqual(len(data.upgrades.separate_traces), 2)
        self.assertEqual(len(data.upgrades.separate_traces[0].points), 1)

    def test_separate_and_ordinary_endpoints_share_the_identity_graph(self):
        result = assemble_routing(prepare_core(design()))
        pair = result.document.one('/Board/DifferentialPairs/DifferentialPair')
        center = pair.one('Segments/Segment/CenterPoints/CenterPoint')
        positive = pair.one('PosSeparateTraces/PosTrace')
        negative = pair.one('NegSeparateTraces/NegTrace')
        self.assertIs(positive['Target1'], center.one('PosPoints/PosPoint'))
        self.assertIs(negative['Target1'], center.one('NegPoints/NegPoint'))
        self.assertIs(positive['Target2'], result.core.pads[17, 9])
        self.assertIs(negative['Target2'], result.core.pads[17, 11])
        self.assertIs(result.traces[73, 53]['Target1'], positive.one('Points/Point'))
        segment = center.parent.parent
        self.assertIs(segment['PosTrace'], result.traces[73, 53])
        self.assertEqual(segment['PosTraceIndex'], 0)
        self.assertIs(center['PosStartPoint'], result.traces[73, 53].one('Points/Point[1]'))
        self.assertIs(center['PosEndPoint'], result.traces[73, 53].one('Points/Point[2]'))
        self.assertIsNone(segment.child('PosTrace'))
        self.assertIsNone(center.child('PosTrace_StartPoint'))
        self.assertIs(positive['NetTrace'], result.traces[73, 53])
        self.assertIs(result.traces[73, 53]['SeparateTrace'], positive)
        self.assertEqual(positive['TraceId'], 0)
        # Cache suppression is a format projection, not a loss of model truth.
        self.assertEqual(result.traces[73, 53]['PairSeparateTrace'], 0)
        self.assertEqual(peer_backlink(result.traces[73, 53]), -1)
        self.assertFalse(result.document.complete)

    def test_paired_pads_keep_identities_after_component_and_pad_reordering(self):
        result = assemble_routing(prepare_core(design(routes=False)))
        document = result.document
        row = document.one('/Board/DifferentialPairs/DifferentialPair/PadPoints/PadPoint')
        pad = result.core.pads[17, 9]
        self.assertIs(row['PosPad'], pad)
        self.assertIs(row['NegPad'], result.core.pads[17, 11])
        self.assertEqual((row['PosComponentIndex'], row['PosPadIndex']), (0, 0))
        self.assertIsNone(row.child('PosComp'))
        self.assertIsNone(row.child('PosPad'))
        component = result.core.components[17]
        component.parent.append(new_component('Other', 'U1'))
        component.move_to(component.parent)
        pad.move_to(pad.parent)
        self.assertEqual((row['PosComponentIndex'], row['PosPadIndex']), (1, 1))
        self.assertIs(row['PosPad'], pad)
        # This deliberately small ASC fixture does not include every footprint
        # setting. Validate its relationship graph, not complete-file eligibility.
        document._validate_relationships(document)

    def test_pair_net_and_pad_assignment_changes_reject_contradictions_atomically(self):
        result = assemble_routing(prepare_core(design(routes=False)))
        pair = result.document.one('/Board/DifferentialPairs/DifferentialPair')
        row = pair.one('PadPoints/PadPoint')
        positive, negative = pair['PosNet'], pair['NegNet']
        with self.assertRaisesRegex(ReferenceError, 'paired pad'):
            pair['PosNet'] = negative
        self.assertIs(pair['PosNet'], positive)
        with self.assertRaisesRegex(ReferenceError, 'paired pad'):
            row['PosPad']['Net'] = negative
        self.assertIs(row['PosPad']['Net'], positive)
        with self.assertRaisesRegex(ReferenceError, 'corresponding pair net'):
            row['PosPad'] = row['NegPad']
        self.assertIs(row['PosPad'], result.core.pads[17, 9])
        result.document._validate_relationships(result.document)

    def test_incorrect_counts_rows_and_aliases_are_rejected(self):
        text = design()
        invalid = (
            text.replace('(PadPoints 1', '(PadPoints 2'),
            text.replace('(pt 17 9 17 11)', '(pt 17 9 17.5 11)'),
            text.replace('(PosPoints 1', '(PosPoints 2'),
            text.replace('(Layer 0)', '(Layer 0) (Lay 0)'),
            text.replace('(PadPoints_Auto "Y")', '(PadPoints_Auto "bad")'),
            text.replace('(Point 1.25 2.5', '(pt 1.25 2.5'),
        )
        for value in invalid:
            with self.subTest(value=value[-120:]), self.assertRaises(PcbError):
                prepare_core(value)

    def test_unresolved_and_cross_net_paired_pads_fail_before_binding(self):
        for replacement in ('17 999 17 11', '17 11 17 9'):
            with self.subTest(replacement=replacement), self.assertRaises(PcbError):
                assemble_routing(prepare_core(design().replace('pt 17 9 17 11', 'pt '+replacement)))

    def test_segment_trace_selectors_use_saved_keys_and_ranges_use_point_positions(self):
        text = design()
        for bad in (text.replace('(PosLine 53)', '(PosLine 0)'),):
            with self.subTest(bad=bad[-120:]), self.assertRaises(PcbError):
                assemble_routing(prepare_core(bad))
        result = assemble_routing(prepare_core(text))
        row = result.document.one('/Board/DifferentialPairs/DifferentialPair/Segments/Segment/CenterPoints/CenterPoint')
        target = row['PosEndPoint']
        target.move_to(target.parent, 0)
        self.assertEqual(row['PosTrace_EndPoint'], 0)
        self.assertIs(row['PosEndPoint'], target)

    def test_peer_keys_are_resolved_and_obsolete_inverse_cache_is_not_authoritative(self):
        text = design()
        with self.assertRaisesRegex(PcbError, 'peer key 0'):
            assemble_routing(prepare_core(text.replace('(NetLine_Link 53)', '(NetLine_Link 0)')))
        result = assemble_routing(prepare_core(text.replace('(PairLine_Link -1)', '(PairLine_Link 999)')))
        ordinary = result.traces[73, 53]
        self.assertIs(ordinary['SeparateTrace']['NetTrace'], ordinary)
        self.assertIsNone(ordinary.child('PairSeparateTrace'))
        self.assertIsNone(ordinary['SeparateTrace'].child('TraceId'))
        self.assertEqual(ordinary['PairSeparateTrace'], 0)
        self.assertEqual(peer_backlink(ordinary), -1)

    def test_ambiguous_ordinary_peer_is_rejected(self):
        source = loads(design())
        first = source.one('/Board/DifferentialPairs/DifferentialPair/SeparateLines_Pos/Line_Pos')
        second = first.clone()
        second.one('OldNumber').set_values(64)
        second.move_to(first.parent)
        with self.assertRaisesRegex(PcbError, 'same ordinary peer'):
            assemble_routing(prepare_core(dumps(source, preserve=False)))

    def test_segment_end_dialects_bind_paired_pads_and_other_segment_centers(self):
        source = loads(design())
        first = source.one('/Board/DifferentialPairs/DifferentialPair/Segments/Segment')
        first.clone().move_to(first.parent)
        first.one('StartSegment').set_values(1)
        first.one('StartPoint').set_values(0)
        result = assemble_routing(prepare_core(dumps(source, preserve=False)))
        pair = result.document.one('/Board/DifferentialPairs/DifferentialPair')
        first, second = pair.select('Segments/Segment')
        self.assertIs(first['Start'], second.one('CenterPoints/CenterPoint'))
        self.assertIs(first['End'], pair.one('PadPoints/PadPoint'))
        self.assertEqual((first['StartSegment'], first['StartPoint']), (1, 0))
        self.assertEqual(first['EndSegment'], -1)
        self.assertIsNone(first.child('StartPoint'))
        self.assertIsNone(first.child('StartSegment'))
        second.move_to(second.parent, 0)
        self.assertEqual(first['StartSegment'], 0)

    def test_invalid_segment_end_targets_fail_and_unused_slots_are_consumed(self):
        text = design()
        for bad in (text.replace('(StartSegment -1)', '(StartSegment 99)'),
                    text.replace('(EndPoint 0)', '(EndPoint 99)')):
            with self.subTest(bad=bad[-100:]), self.assertRaisesRegex(PcbError, 'segment .* target'):
                assemble_routing(prepare_core(bad))
        text = text.replace('(StartPoint 0)', '(StartPoint -1)').replace('(StartSegment -1)', '(StartSegment 99)')
        result = assemble_routing(prepare_core(text))
        first = result.document.one('/Board/DifferentialPairs/DifferentialPair/Segments/Segment')
        self.assertIsNone(first['Start'])
        self.assertEqual((first['StartPoint'], first['StartSegment']), (-1, -1))

    def test_point_membership_binds_a_center_or_actual_side_point(self):
        source = loads(design())
        rows = source.select('/Board/Nets/Net[1]/Lines/Line/Points/pt')
        for point, sub in zip(rows, (0, -1)):
            point.set_argument(15, 0)
            point.set_argument(18, sub)
        result = assemble_routing(prepare_core(dumps(source, preserve=False)))
        center = result.document.one('/Board/DifferentialPairs/DifferentialPair/Segments/Segment/CenterPoints/CenterPoint')
        points = result.traces[73, 53].select('Points/Point')
        self.assertIs(points[0]['PairTarget'], center.one('PosPoints/PosPoint'))
        self.assertIs(points[1]['PairTarget'], center)
        self.assertEqual((points[0]['PairPoint'], points[0]['PairSubPoint']), (0, 0))
        self.assertTrue(all(point.child('PairPoint') is None for point in points))

    def test_connection_sequence_counters_are_not_invented_side_points(self):
        source = loads(design())
        center = source.one('/Board/DifferentialPairs/DifferentialPair/Segments/Segment/CenterPoints/CenterPoint')
        center.one('Type').set_values(2)
        for index, point in enumerate(source.select('/Board/Nets/Net[1]/Lines/Line/Points/pt')):
            point.set_argument(15, 0)
            point.set_argument(18, index+100)
        result = assemble_routing(prepare_core(dumps(source, preserve=False)))
        center = result.document.one('/Board/DifferentialPairs/DifferentialPair/Segments/Segment/CenterPoints/CenterPoint')
        points = result.traces[73, 53].select('Points/Point')
        self.assertTrue(all(point['PairTarget'] is center for point in points))
        self.assertEqual([point['PairSubPoint'] for point in points], [-1, -1])
        self.assertEqual(len(center.select('PosPoints/PosPoint')), 1)

    def test_invalid_member_center_and_side_indices_fail_without_guessing(self):
        source = loads(design())
        point = source.one('/Board/Nets/Net[1]/Lines/Line/Points/pt[1]')
        for ci, sub in ((99, -1), (0, 99)):
            point.set_argument(15, ci)
            point.set_argument(18, sub)
            with self.subTest(center=ci, sub=sub), self.assertRaisesRegex(PcbError, 'unresolved saved'):
                assemble_routing(prepare_core(dumps(source, preserve=False)))

    def test_tags_outside_segment_geometry_are_unused_compatibility_values(self):
        source = loads(design())
        segment = source.one('/Board/DifferentialPairs/DifferentialPair/Segments/Segment')
        segment.one('PosLine').set_values(-1)
        center = segment.one('CenterPoints/CenterPoint')
        for end in ('Start', 'End'):
            center.one('PosLine_'+end+'Point').set_values(-1)
        for point in source.select('/Board/Nets/Net[1]/Lines/Line/Points/pt'):
            point.set_argument(15, 99)
            point.set_argument(18, 99)
        result = assemble_routing(prepare_core(dumps(source, preserve=False)))
        points = result.traces[73, 53].select('Points/Point')
        self.assertTrue(all(point['PairTarget'] is None for point in points))
        self.assertTrue(all(point.child('PairPoint') is None for point in points))


if __name__ == '__main__':
    unittest.main()
