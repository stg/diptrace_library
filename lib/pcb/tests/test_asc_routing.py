"""ASC traces use the shared identity graph and full named point geometry."""
from decimal import Decimal
import unittest

from lib.common.asc import loads, dumps
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.asc.routing import unpack_trace
from lib.pcb.formats.assembly.routing import assemble_routing
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_asc_core import fixture


POINT = '1.25 2.5 0 3 0.75 12 4 2 "Y" "N" -1 8 0 1 "Y" -1 3.5 4.5 2 "N" 1 0.37'
TRACE = '''(Line
  (Connect1 17) (ConnectL1 9) (ConnectP1 -1)
  (Connect2 17) (ConnectP2 11) (ConnectL2 -1)
  (ConnectedToLine1 "N") (ConnectedToLine2 "N")
  (FreeEnd1 "N") (FreeEnd21 "N") (Selected "N") (Group -1)
  (OldNumber 53) (PairLine_Link -1) (ConnectMode1 0) (ConnectMode2 0)
  (Points (pt '''+POINT+''') (pt 4 5 0 0 0.5 0 0 0 "N" "N" -1 0 0 0 "N" -1 0 0 0 "N" 0 0))
  (Teardrops_Connected (pt 3)))'''
SEPARATE_POINT = '1.25 2.5 0 3 0.75 12 "Y" 2 "N" -1 8 0 1 "Y" "N" 1 0.37'
SEPARATE_TRACE = '''(Line_Pos
  (Connect1 17) (ConnectL1 9) (ConnectP1 -1)
  (Connect2 17) (ConnectL2 11) (ConnectP2 -1)
  (ConnectMode1 0) (ConnectMode2 0) (Selected "N") (Group -1)
  (NetLine_Link 53) (OldNumber 61) (Points (Point '''+SEPARATE_POINT+''')))'''


def design(*, second=False, first=TRACE):
    doc = loads(fixture())
    lines = doc.one('/Board/Nets/Net/Lines')
    loads(first).one('/Line').move_to(lines)
    if second:
        source = loads(TRACE)
        trace = source.one('/Line')
        trace.one('OldNumber').set_values(99)
        trace.one('ConnectMode1').set_values(1)
        trace.one('Connect1').set_values(73)
        trace.one('ConnectL1').set_values(53)
        trace.one('ConnectP1').set_values(1)
        trace.one('ConnectMode2').set_values(7)
        trace.move_to(lines)
    return dumps(doc, preserve=False)


class AscRoutingTests(unittest.TestCase):
    def test_unavailable_phase_markers_share_the_text_and_binary_assembly_rule(self):
        for marker in ('-100000', '-100001'):
            with self.subTest(marker=marker):
                text = TRACE.replace('3.5 4.5 2', f'{marker} -99999.9 2')
                result = assemble_routing(prepare_core(design(first=text)))
                point = result.traces[73, 53].one('Points/Point[1]')
                self.assertIsNone(point.get('PhaseFwd'))
                self.assertIsNone(point.child('PhaseFwd'))
                self.assertEqual(point['PhaseBack'], Decimal('-99999.9'))

    def test_pad_endpoints_bind_through_the_ordinary_second_endpoint_spelling(self):
        result = assemble_routing(prepare_core(design()))
        trace = result.traces[73, 53]
        self.assertIs(trace['Target1'], result.core.pads[17, 9])
        self.assertIs(trace['Target2'], result.core.pads[17, 11])
        self.assertEqual((trace['Connected1'], trace['Object1'], trace['SubObject1']), ('Pad', 0, 1))
        for name in ('Connect1', 'ConnectL2', 'ConnectP2', 'ConnectedToLine1', 'FreeEnd21', 'OldNumber'):
            self.assertIsNone(trace.child(name))
        first = result.core.pads[17, 9]
        first.move_to(first.parent)
        self.assertIs(trace['Target1'], first)
        self.assertEqual(trace['SubObject1'], 2)

    def test_point_fields_preserve_authored_geometry_and_omit_repeated_via_values(self):
        data = prepare_core(design())
        point = data.board.one('Nets/Net/Traces/Trace/Points/Point[1]')
        self.assertEqual((point['X'], point['Y'], point['Width']),
                         (Decimal('1.25'), Decimal('2.5'), Decimal('.75')))
        self.assertEqual((point['Jumper'], point['Arc'], point['Selected']), (2, False, True))
        self.assertEqual((point['PhaseFwd'], point['PhaseBack'], point['PairSubPoint']),
                         (Decimal('3.5'), Decimal('4.5'), 2))
        self.assertEqual((point['Meander'], point['MeanderAngle']), (1, Decimal('.37')))
        self.assertEqual(point.values, (0,))
        self.assertIsNone(point.child('ViaSize'))
        self.assertIsNone(point.child('Direction'))
        self.assertEqual(data.board.one('Nets/Net/Traces/Trace/ConnectedTeardrops/Item').values, (3,))

    def test_trace_point_targets_survive_trace_and_point_reordering(self):
        result = assemble_routing(prepare_core(design(second=True)))
        first, second = result.traces[73, 53], result.traces[73, 99]
        target = first.one('Points/Point[2]')
        self.assertIs(second['Target1'], target)
        self.assertEqual(second['Connected2'], 'Free')
        target.move_to(target.parent, 0)
        first.move_to(first.parent)
        self.assertIs(second['Target1'], target)
        self.assertEqual((second['SubObject1'], second['Point1']), (1, 0))

    def test_arc_is_independent_of_the_repeated_through_via_choice(self):
        for through in ('Y', 'N'):
            for arc in ('Y', 'N'):
                with self.subTest(through=through, arc=arc):
                    text = TRACE.replace('2 "Y" "N" -1', f'2 "{through}" "{arc}" -1')
                    result = assemble_routing(prepare_core(design(first=text)))
                    point = result.traces[73, 53].one('Points/Point[1]')
                    self.assertEqual(point['Arc'], arc == 'Y')
                    self.assertIsNone(point.child('ThroughVia'))

    def test_separate_trace_endpoint_dialect_keeps_its_own_column_names(self):
        row = loads(SEPARATE_TRACE).one('/Line_Pos')
        prepared = unpack_trace(row, separate=True)
        self.assertEqual((prepared.trace['SubObject2'], prepared.trace['Point2']), (11, -1))
        self.assertEqual(prepared.trace['TraceId'], 53)
        self.assertFalse(prepared.points[0]['Arc'])
        self.assertTrue(prepared.points[0]['Selected'])

    def test_current_connection_mode_wins_over_old_compatibility_flags(self):
        text = TRACE.replace('(FreeEnd1 "N")', '(FreeEnd1 "Y")')
        result = assemble_routing(prepare_core(design(first=text)))
        self.assertEqual(result.traces[73, 53]['Connected1'], 'Pad')

    def test_bad_modes_rows_booleans_and_saved_keys_fail_explicitly(self):
        invalid = (
            TRACE.replace('(ConnectMode1 0)', '(ConnectMode1 2)'),
            TRACE.replace(POINT, POINT.rsplit(' ', 1)[0]),
            TRACE.replace('2 "Y" "N" -1', '2 "invalid" "N" -1'),
            TRACE.replace('(OldNumber 53)', '(OldNumber "bad")'),
            TRACE.replace('(ConnectMode1 0)', '(ConnectMode1 0) (Connected1 0)'),
        )
        for text in invalid:
            with self.subTest(text=text[:35]), self.assertRaises(PcbError):
                prepare_core(design(first=text))
        with self.assertRaisesRegex(PcbError, 'unresolved saved Pad endpoint'):
            assemble_routing(prepare_core(design(first=TRACE.replace('(ConnectL1 9)', '(ConnectL1 999)'))))


if __name__ == '__main__':
    unittest.main()
