"""Differential XML output preserves edited relationships and supplied geometry."""
from decimal import Decimal
import unittest

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.pcb.formats.asc.pair_projection import project_pairs as asc_pairs
from lib.pcb.tests.test_cache_projection import signature
from lib.pcb.tests.test_dipxml_library import read
from lib.pcb.tests.test_dipxml_pairs import source
from lib.pcb.tests.test_xml_routing_output import reopen, with_component_library


PAIR = '/Board/DifferentialPairs/DifferentialPair'


def design(text=None, *, report=None):
    return read(with_component_library(source() if text is None else text),
                report=ConversionReport() if report is None else report)


class XmlPairOutputTests(unittest.TestCase):
    def assert_facts(self, actual, expected):
        self.assertEqual(actual.keys(), expected.keys())
        for name, value in expected.items():
            if isinstance(value, (int, Decimal)) and not isinstance(value, bool):
                self.assertLessEqual(abs(actual[name]-value), Decimal('1e-23'), name)
            else:
                self.assertEqual(actual[name], value, name)

    def test_pairs_and_ordinary_memberships_survive_units_and_repeated_conversion(self):
        document = design()
        roots = ('/Board/Nets', '/Board/DifferentialPairs')
        expected = {path: signature(document.one(path)) for path in roots}
        unchanged = model_text(document, preserve=False)
        for units in ('mm', 'mil', 'inch'):
            current = document
            for _ in range(3):
                current, _ = reopen(current, units=units)
                for path in roots:
                    self.assert_facts(signature(current.one(path)), expected[path])
                current.references.validate()
        self.assertEqual(model_text(document, preserve=False), unchanged)

    def test_reordered_pads_centers_and_route_points_keep_their_targets(self):
        document = design()
        pair = document.one(PAIR)
        segment = pair.one('Segments/Segment')
        center = segment.one('CenterPoints/CenterPoint')
        document.copy(center, parent=center.parent)
        center.move_to(center.parent, 1)
        pad = pair.one('PadPoints/PadPoint')['PosPad']
        pad.move_to(pad.parent, 1)
        point = center['PosEndPoint']
        point.move_to(point.parent, 0)
        expected = signature(document.one('/Board'))
        rebuilt, _ = reopen(document)
        for path in ('Nets', 'DifferentialPairs'):
            self.assert_facts(signature(rebuilt.one('/Board/'+path)),
                              signature(document.one('/Board/'+path)))
        center = rebuilt.one(PAIR+'/Segments/Segment/CenterPoints/CenterPoint[2]')
        trace = rebuilt.one(PAIR)['PosNet'].one('Traces/Trace[1]')
        self.assertIs(center['PosEndPoint'], trace.one('Points/Point[1]'))
        self.assertIs(trace.one('Points/Point[2]')['PairTarget'], center.one('PosPoints/PosPoint'))
        self.assertEqual(signature(document.one('/Board')), expected)
        rebuilt.references.validate()

    def test_center_and_side_shield_assignments_include_valid_zero(self):
        text = source().replace('PosTraceSide="-1"', 'PosTraceSide="-1" PosShieldGroup="0" NegShieldGroup="7"')
        text = text.replace('PosPoint X=', 'PosPoint ShieldGroup="0" X=')
        text = text.replace('NegPoint X=', 'NegPoint ShieldGroup="9" X=')
        document = design(text)
        center = document.one(PAIR+'/Segments/Segment/CenterPoints/CenterPoint')
        self.assertEqual((center['PosShieldGroup'], center['NegShieldGroup']), (0, 7))
        self.assertEqual(center.one('PosPoints/PosPoint')['ShieldGroup'], 0)
        rebuilt, output = reopen(document)
        self.assert_facts(signature(rebuilt.one(PAIR)), signature(document.one(PAIR)))
        projected = output.one('/Source/Board/DifferentialPairs/DifferentialPair/Segments/Segment/CenterPoints/CenterPoint')
        self.assertEqual(projected.scalar('PosShieldGroup'), 0)
        report = ConversionReport()
        asc_pairs(document.one('/Board'), report=report)
        self.assertEqual({notice.rule for notice in report.warnings}, {'pair-shield-group', 'trace-shield-group'})

    def test_unresolved_range_survives_as_an_explicit_current_selection(self):
        document = design(source().replace('PosTrace_EndPoint="1"', 'PosTrace_EndPoint="76"'))
        report = ConversionReport()
        rebuilt, _ = reopen(document, report=report)
        center = rebuilt.one(PAIR+'/Segments/Segment/CenterPoints/CenterPoint')
        self.assertEqual(center['UnresolvedPosEndPointIndex'], 76)
        self.assertIn('unresolved-pair-range', {notice.rule for notice in report.warnings})
        center['PosEndPoint'] = center['PosStartPoint']
        self.assertIsNone(center.child('UnresolvedPosEndPointIndex'))
        rebuilt.references.validate()

    def test_connection_counters_and_separate_calculations_are_export_views(self):
        text = source().replace('Type="Unpaired"', 'Type="Connection"').replace('PairSubPoint="0"', 'PairSubPoint="999"')
        document = design(text)
        separate_point = document.one(PAIR+'/PosSeparateTraces/PosTrace/Points/Point[1]')
        separate_point['PhaseFwd'] = Decimal('2.5')
        before = model_text(document, preserve=False)
        report = ConversionReport()
        rebuilt, output = reopen(document, report=report)
        point = rebuilt.one(PAIR)['PosNet'].one('Traces/Trace[1]/Points/Point[1]')
        self.assertIs(point['PairTarget'], rebuilt.one(PAIR+'/Segments/Segment/CenterPoints/CenterPoint'))
        self.assertEqual(output.one('/Source/Board/Nets/Net[1]/Traces/Trace[1]/Points/Point[1]').scalar('PairSubPoint'), 1)
        self.assertIsNone(rebuilt.one(PAIR+'/PosSeparateTraces/PosTrace/Points/Point[1]').get('PhaseFwd'))
        self.assertIn('separate-phase-calculation', {notice.rule for notice in report.infos})
        self.assertEqual(model_text(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
