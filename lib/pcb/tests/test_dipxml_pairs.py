"""XML paired geometry shares editable identities with ordinary routing."""
from decimal import Decimal
import unittest

from lib.common.conversion import ConversionReport, import_diagnostics
from lib.common.references import ReferenceError
from lib.pcb.formats.assembly.board_rules import assemble_rules
from lib.pcb.tests.test_dipxml_electrical import prepared
from lib.pcb.tests.test_dipxml_settings import source as settings_source


PAIR = '''<DifferentialPairs><DifferentialPair Id="100" PosNet="7" NegNet="98" NetClass="70"
      RouteMode="Full Reroute" AutoPadPoints="N" CustomColor="Y" TraceColor="123">
  <Name>Data pair</Name>
  <PadPoints><PadPoint Id="42" PosComp="8" PosPad="17" NegComp="8" NegPad="41"/></PadPoints>
  <Segments><Segment PosTrace="91" NegTrace="-1" StartPoint="0" EndPoint="0" StartSegment="-1" EndSegment="-1">
    <CenterPoints><CenterPoint X="2" Y="3" Lay="30" ViaStyle="62" Type="Unpaired" PosTraceSide="-1"
         PosTrace_StartPoint="0" PosTrace_EndPoint="1" NegTrace_StartPoint="-1" NegTrace_EndPoint="-1"
         Necked="Y" PhaseError="N">
      <PosPoints><PosPoint X="0.1" Y="0.2" Lay="30" ViaStyle="17" Necked="Y" Meander="2"
          MeanderAngle="7.8" Arc="Y"/></PosPoints>
      <NegPoints><NegPoint X="-0.1" Y="-0.2" Lay="30" ViaStyle="-1"/></NegPoints>
    </CenterPoint></CenterPoints>
  </Segment></Segments>
  <PosSeparateTraces><PosTrace Id="77" Connected1="Segment" Object1="0" SubObject1="0" Point1="0"
        Connected2="Pad" Object2="8" SubObject2="17" Point2="-1" TraceId="13">
    <Points><Point X="3" Y="4" Lay="30" Width="0.3" ViaStyle="17" Necked="Y"/>
      <Point X="5" Y="6" Lay="30" Width="0.3" ViaStyle="-1"/></Points>
  </PosTrace></PosSeparateTraces>
  <NegSeparateTraces><NegTrace Id="88" Connected1="Segment" Object1="0" SubObject1="0" Point1="0"
        Connected2="Pad" Object2="8" SubObject2="41" TraceId="-1">
    <Points><Point X="-3" Y="-4" Lay="30" Width="0.3" ViaStyle="-1"/></Points>
  </NegTrace></NegSeparateTraces>
</DifferentialPair></DifferentialPairs>'''


def source():
    text = settings_source().replace('Pad Id="41" NetId="-1"', 'Pad Id="41" NetId="98"')
    text = text.replace('</Nets>', '''<Net Id="98" NetClass="70"><Name>Negative</Name>
      <Pads><Item Comp="8" Pad="41"/></Pads><Traces/></Net></Nets>''')
    text = text.replace('Id="40"', 'Id="40" PairPoint="0" PairSubPoint="0"')
    text = text.replace('Connected2="Free"', 'Connected2="Separate Trace" SubObject2="77" Point2="0"', 1)
    return text.replace('</Board>', PAIR+'</Board>')


def design(text=None, *, report=None):
    operation = lambda text: assemble_rules(prepared(text)).document
    return import_diagnostics('dipxml')(operation)(source() if text is None else text, report=report)


class PcbXmlPairTests(unittest.TestCase):
    def test_routing_lengths_follow_each_xml_version_convention(self):
        for version, width, phase in (('5.3.4.9', Decimal('.3'), Decimal('.4')),
                                      ('5.3.5.0', Decimal('.9'), Decimal('1.2')),
                                      ('', Decimal('.9'), Decimal('1.2'))):
            with self.subTest(version=version):
                text = source().replace('Version="5.3.5.1"', f'Version="{version}"')
                text = text.replace('Id="40"', 'Id="40" PhaseFwd="0.4" PhaseBack="-0.2"')
                document = design(text, report=ConversionReport())
                ordinary = document.one('/Board/Nets/Net[1]/Traces/Trace[1]/Points/Point[1]')
                separate = document.one('/Board/DifferentialPairs/DifferentialPair/PosSeparateTraces/PosTrace/Points/Point[1]')
                self.assertEqual(ordinary['Width'], Decimal('.9'))
                self.assertEqual(separate['Width'], width)
                self.assertEqual(ordinary['PhaseFwd'], phase)
                self.assertEqual(ordinary['PhaseBack'], -phase/2)
                self.assertIsNone(separate.get('PhaseFwd'))

    def test_unavailable_phase_lengths_are_absent_editable_values(self):
        for marker in ('-100000', '-100001'):
            with self.subTest(marker=marker):
                # In the earlier convention phase lengths are already in the
                # model's length units. Zero and signed measured values remain.
                text = source().replace('Version="5.3.5.1"', 'Version="4.3.0.5"')
                text = text.replace('Id="40"', f'Id="40" PhaseFwd="{marker}" PhaseBack="0"')
                document = design(text, report=ConversionReport())
                node = document.one('/Board/Nets/Net[1]/Traces/Trace[1]/Points/Point[1]')
                self.assertIsNone(node.get('PhaseFwd'))
                self.assertIsNone(node.child('PhaseFwd'))
                self.assertEqual(node['PhaseBack'], 0)
                node['PhaseFwd'] = Decimal('-.2')
                self.assertEqual(node['PhaseFwd'], Decimal('-.2'))
                del node['PhaseFwd']
                self.assertIsNone(node.get('PhaseFwd'))
                document.references.validate()

    def test_named_geometry_and_rule_choices_reach_current_records(self):
        document = design(report=ConversionReport())
        pair = document.one('/Board/DifferentialPairs/DifferentialPair')
        segment = pair.one('Segments/Segment')
        center = segment.one('CenterPoints/CenterPoint')
        side = center.one('PosPoints/PosPoint')
        self.assertEqual((pair['Id'], pair['Name'], pair['RouteMode'], pair['AutoPadPoints']),
                         (0, 'Data pair', 2, False))
        self.assertEqual((pair['CustomColor'], pair['TraceColor']), (True, 123))
        self.assertEqual((center['X'], center['Y'], center['Type'], center['Necked']), (6, -9, 3, True))
        self.assertEqual((side['X'], side['Y'], side['Meander'], side['MeanderAngle']),
                         (Decimal('.3'), Decimal('-.6'), 2, Decimal('7.8')))
        self.assertTrue(side['Arc'])
        self.assertIs(center['Layer'], document.one('/Board/Layers/Layer[1]'))
        self.assertIs(center['Via'], document.one('/Board/ViaStyles/ViaStyle[1]'))
        self.assertIs(pair['Class'], document.one('/Board/NetClasses/NetClass[2]'))
        self.assertFalse(document.complete)

    def test_endpoints_membership_ranges_and_peers_bind_identity_domains(self):
        document = design(report=ConversionReport())
        pair = document.one('/Board/DifferentialPairs/DifferentialPair')
        segment = pair.one('Segments/Segment')
        center = segment.one('CenterPoints/CenterPoint')
        positive, negative = pair.one('PosSeparateTraces/PosTrace'), pair.one('NegSeparateTraces/NegTrace')
        first, other = pair['PosNet'].select('Traces/Trace')
        pads = document.select('/Board/Components/Component/Pattern/Pads/Pad')
        row = pair.one('PadPoints/PadPoint')
        self.assertIs(row['PosPad'], pads[0])
        self.assertIs(row['NegPad'], pads[1])
        self.assertIs(segment['Start'], row)  # PadPoint Id=42 is an output counter.
        self.assertIs(segment['PosTrace'], first)
        self.assertIs(center['PosEndPoint'], first.one('Points/Point[2]'))
        self.assertIs(first.one('Points/Point[1]')['PairTarget'], center.one('PosPoints/PosPoint'))
        self.assertIs(first['Target2'], positive.one('Points/Point[1]'))
        self.assertIs(positive['NetTrace'], other)
        self.assertIs(positive['Target1'], center.one('PosPoints/PosPoint'))
        self.assertIs(negative['Target1'], center.one('NegPoints/NegPoint'))
        self.assertIs(negative['Target2'], pads[1])
        self.assertTrue(positive.one('Points/Point[1]')['PairNecked'])
        self.assertIsNone(segment.child('PosTrace'))
        self.assertIsNone(center.child('PosTrace_EndPoint'))
        document.references.validate()

    def test_point_order_not_point_id_counters_selects_geometry(self):
        text = source().replace('Point Id="90"', 'Point Id="40"').replace('Point Id="50"', 'Point')
        document = design(text, report=ConversionReport())
        first, other = document.one('/Board/DifferentialPairs/DifferentialPair')['PosNet'].select('Traces/Trace')
        self.assertIs(other['Target1'], first.one('Points/Point[2]'))
        self.assertEqual([point['Id'] for point in first.select('Points/Point')], [0, 1])

    def test_edits_and_clone_reuse_existing_pair_constraints(self):
        document = design(report=ConversionReport())
        center = document.one('/Board/DifferentialPairs/DifferentialPair/Segments/Segment/CenterPoints/CenterPoint')
        target = center['PosEndPoint']
        target.move_to(target.parent, 0)
        self.assertIs(center['PosEndPoint'], target)
        self.assertEqual(center['PosTrace_EndPoint'], 0)
        self.assertEqual((center['X'], center['Y']), (6, -9))
        clone = document.clone()
        copied = clone.one('/Board/DifferentialPairs/DifferentialPair/Segments/Segment/CenterPoints/CenterPoint')
        self.assertIsNot(copied['PosEndPoint'], target)
        with self.assertRaises(ReferenceError):
            copied['PosEndPoint'] = target
        clone.references.validate()

    def test_unavailable_ranges_use_the_same_report_and_repair_path_as_binary(self):
        report = ConversionReport()
        document = design(source().replace('PosTrace_EndPoint="1"', 'PosTrace_EndPoint="76"'), report=report)
        center = document.one('/Board/DifferentialPairs/DifferentialPair/Segments/Segment/CenterPoints/CenterPoint')
        self.assertEqual(center['UnresolvedPosEndPointIndex'], 76)
        self.assertIn('unresolved-pair-range', {notice.rule for notice in report.warnings})
        center['PosEndPoint'] = center['PosStartPoint']
        self.assertEqual(center['PosTrace_EndPoint'], 0)
        self.assertEqual(document.references.issues, [])

    def test_connection_membership_counters_do_not_invent_side_points(self):
        text = source().replace('Type="Unpaired"', 'Type="Connection"').replace('PairSubPoint="0"', 'PairSubPoint="999"')
        document = design(text, report=ConversionReport())
        pair = document.one('/Board/DifferentialPairs/DifferentialPair')
        center = pair.one('Segments/Segment/CenterPoints/CenterPoint')
        point = pair['PosNet'].one('Traces/Trace[1]/Points/Point[1]')
        self.assertIs(point['PairTarget'], center)
        self.assertEqual(point['PairSubPoint'], -1)

    def test_invalid_keys_side_assignments_and_unknown_enums_are_not_guessed(self):
        for before, after in (('PosNet="7"', 'PosNet="999"'),
                              ('PosPad="17" NegComp="8" NegPad="41"', 'PosPad="17" NegComp="8" NegPad="17"'),
                              ('PosTrace="91"', 'PosTrace="0"'),
                              ('TraceId="13"', 'TraceId="99"'),
                              ('MeanderAngle="7.8"', 'Unknown="7.8"'),
                              ('Type="Unpaired"', 'Type="Unknown"')):
            with self.subTest(after=after), self.assertRaises(ValueError):
                design(source().replace(before, after), report=ConversionReport())


if __name__ == '__main__':
    unittest.main()
