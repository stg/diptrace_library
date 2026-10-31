"""ASC/XML check results select the same pads, traces, layers and classes."""
from decimal import Decimal
import unittest

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport, import_diagnostics
from lib.common.references import ReferenceError
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.tests.test_asc_graphics import fixture as asc_fixture
from lib.pcb.tests.test_dipxml_graphics import source as xml_fixture
from lib.pcb.tests.test_dipxml_electrical import prepared


XML = '''<DesignErrors><DesignError Id="99" X="1" Y="2" Type="Clearance" Value="0.1" Rule="0.2"
  RuleType="NetClass2" RuleLay="8" ObjectType1="PadHole" Object1="8" SubObject1="17"
  ObjectType2="Trace" Object2="7" SubObject2="91" Point2="1"
  ObjectNetClass1="4" ObjectNetClass2="70"><Lays><Item>N</Item><Item>Y</Item><Item>N</Item></Lays>
</DesignError></DesignErrors>'''


def xml_source():
    return xml_fixture().replace('</Board>', XML+'</Board>')


class DrcResultInputTests(unittest.TestCase):
    def test_xml_units_keys_and_snapshot_fields_enter_the_same_graph(self):
        result = assemble_graphics(prepared(xml_source()))
        document = result.document
        error = document.one('/Board/DesignErrors/DesignError')
        self.assertEqual((error['Id'], error['X'], error['Y'], error['Value'], error['Rule']),
                         (0, 3, -6, Decimal('.3'), Decimal('.6')))
        self.assertIs(error['Target1'], result.rules.routing.core.pads[8, 1])
        self.assertIs(error['Target2'], result.rules.routing.traces[7, 91].one('Points/Point[2]'))
        self.assertIs(error['RuleLayer'], result.rules.layers[1])
        self.assertIs(error['NetClass1'], result.rules.classes[0])
        self.assertIs(error['NetClass2'], result.rules.classes[1])
        self.assertEqual((error['Object1'], error['SubObject1'], error['Object2'], error['SubObject2']), (0, 0, 0, 0))
        self.assertEqual(error.one('Layers/Layer')['Index'], 1)
        document.references.validate()

    def test_reference_changes_update_selectors_but_not_recorded_threshold(self):
        result = assemble_graphics(prepared(xml_source()))
        document = result.document
        error = document.one('/Board/DesignErrors/DesignError')
        point = error['Target2']
        point.move_to(point.parent, 0)
        result.rules.classes[1].move_to(result.rules.classes[1].parent, 0)
        self.assertEqual((error['Point2'], error['ObjectNetClass2']), (0, 0))
        self.assertEqual(error['Rule'], Decimal('.6'))
        document.references.validate()

    def test_ascii_named_layer_mask_and_rule_layer_alias_are_consumed(self):
        data = asc_fixture()
        error = data.one('/Board').add('DesignErrors').add('DesignError')
        for name, value in dict(Enabled='Y', X=1, Y=2, Type=0, Value=Decimal('.3'), Rule=Decimal('.4'),
                ObjectType1=7, Object1=29, ObjectType2=1, Object2=-1, Point2=-1, RuleLayer=2).items():
            error.add(name, value)
        error.add('Layers', 3).add('pt', 'N').parent.add('pt', 'N').parent.add('pt', 'Y')
        result = assemble_graphics(prepare_core(dumps(data, preserve=False)))
        row = result.document.one('/Board/DesignErrors/DesignError')
        self.assertIs(row['Target1'], result.pours[29])
        self.assertIs(row['Target2'], result.document.one('/Board'))
        self.assertIs(row['RuleLayer'], result.rules.layers[2])
        self.assertEqual(row.one('Layers/Layer')['Index'], 2)
        result.document.references.validate()

    def test_invalid_field_types_and_unknown_error_attributes_do_not_pass_silently(self):
        for old, new in (('RuleLay="8"', 'RuleLay="8.5"'), ('<Item>Y</Item>', '<Item>bad</Item>'),
                         ('Value="0.1"', 'Value="bad"'), ('Type="Clearance"', 'Type="unknown"')):
            with self.subTest(old=old), self.assertRaises(ValueError):
                assemble_graphics(prepared(xml_source().replace(old, new)))
        with self.assertRaises(ValueError):
            assemble_graphics(prepared(xml_source().replace('Id="99"', 'Id="99" Extra="unknown"')))

    def test_unavailable_point_keeps_current_ancestor_positions_and_can_be_resolved(self):
        @import_diagnostics('dipxml')
        def read(text):
            return assemble_graphics(prepared(text)).document
        report = ConversionReport()
        document = read(xml_source().replace('Point2="1"', 'Point2="99"'), report=report)
        error = document.one('/Board/DesignErrors/DesignError')
        unresolved = error.one('UnresolvedTarget2')
        self.assertEqual(unresolved.values, (0, 0, 99, -1))
        self.assertTrue(any(n.rule == 'unresolved-design-error-targets' for n in report.warnings))
        trace = document.one('/Board/Nets/Net/Traces/Trace[1]')
        point = trace.one('Points/Point[2]')
        with self.assertRaises(ReferenceError):
            point.move_to(point.parent, 0)
        error['Target2'] = point
        self.assertIsNone(error.child('UnresolvedTarget2'))
        self.assertFalse(document.references.issues)
        point.move_to(point.parent, 0)
        self.assertEqual(error['Point2'], 0)
        document.references.validate()

    def test_component_drawing_qualifier_selects_position_instead_of_the_xml_component_key(self):
        @import_diagnostics('dipxml')
        def read(text):
            return assemble_graphics(prepared(text)).document
        text = xml_source().replace('ObjectType1="PadHole" Object1="8"',
            'ObjectType1="Shape" Object1="999" ExtObject1="0"')
        report = ConversionReport()
        document = read(text, report=report)
        row = document.one('/Board/DesignErrors/DesignError')
        self.assertIs(row['Target1'], document.one('/Board/Components/Component'))
        self.assertEqual((row['Object1'], row['ExtObject1']), (-1, 0))
        self.assertTrue(any(n.rule == 'design-error-drawing-detail' for n in report.infos))
        report = ConversionReport()
        document = read(text.replace('ExtObject1="0"', 'ExtObject1="8"'), report=report)
        row = document.one('/Board/DesignErrors/DesignError')
        self.assertEqual(row.one('UnresolvedTarget1').values, (-1, -1, -1, 8))
        self.assertTrue(report.warnings)
        row['Target1'] = document.one('/Board/Components/Component')
        self.assertFalse(document.references.issues)
        document.references.validate()


if __name__ == '__main__':
    unittest.main()
