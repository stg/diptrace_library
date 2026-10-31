"""ASC/XML length rules share one PCB authoring representation."""
from decimal import Decimal
import unittest

from lib.common.asc import loads, dumps
from lib.common.conversion import ConversionReport, import_diagnostics
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.assembly.board_rules import assemble_rules
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_asc_rules import fixture as asc_fixture
from lib.pcb.tests.test_dipxml_classes import source as xml_fixture
from lib.pcb.tests.test_dipxml_electrical import prepared


ASC = '''(MainLengthRule "Y" -1 7.62 "N" "Y" -1 0
    (pt 73 17 9 17 11 3.5 "N"))
  (LengthRules (LengthRule "Signals" 10 0.25 "Y" "N" 1 1
    (pt 73 17 11 17 9 3.5 "Y")))'''
XML = '''<MainLengthRule Type="By User"><Name>Y</Name></MainLengthRule>
  <LengthRules><LengthRule Type="By NetClass" FixedLength="2" Delta="0.3" AnyError="Y" NetClass="70">
    <Name>Signals</Name><Rules><Rule NetId="7" Comp1="8" Pad1="17" Comp2="8" Pad2="41"
      Length="1.3" Error="Y"/></Rules></LengthRule></LengthRules>'''


def asc_source():
    source = loads(asc_fixture().replace('(NetClass "Signal"',
        '(NetClass "Signal" (CheckLength "Y") (FixedLength 9) (LengthDelta 0.4)'))
    for node in tuple(loads(ASC).root.children()):
        node.move_to(source.one('/Board'))
    return dumps(source, preserve=False)


def xml_source():
    text = xml_fixture().replace('Pad Id="41" NetId="-1"', 'Pad Id="41" NetId="7"')
    text = text.replace('NetClass Id="70"', 'NetClass Id="70" CheckLength="Y" FixedLength="5" LengthDelta="0.4"')
    return text.replace('</Board>', XML+'</Board>')


class LengthRuleInputTests(unittest.TestCase):
    def test_ascii_columns_preserve_authored_names_and_derive_aggregate_flags(self):
        result = assemble_rules(prepare_core(asc_source()))
        main = result.document.one('/Board/MainLengthRule')
        net_class = result.classes[1]
        results = net_class.one('LengthResults')
        row = main.one('Rules/Rule')
        self.assertEqual((main['Name'], main['AnyError']), ('Y', False))
        self.assertEqual((net_class['Name'], net_class['FixedLength'], net_class['LengthDelta']),
                         ('Signal', 9, Decimal('.4')))
        self.assertTrue(results['AnyError'])
        self.assertEqual(result.document.one('/Board/LengthRules').children(), [])
        self.assertEqual(set(results.schema.fields), {'AnyError'})
        self.assertEqual([node.kind for node in results.children()], ['Rules'])
        self.assertIs(row['Pad1'], result.routing.core.pads[17, 9])
        self.assertEqual(row['Length'], Decimal('3.5'))
        self.assertEqual(main.values, ())
        result.document.references.validate()

    def test_xml_lengths_class_and_pad_keys_map_to_the_current_model(self):
        result = assemble_rules(prepared(xml_source()))
        document = result.document
        main = document.one('/Board/MainLengthRule')
        net_class = result.classes[1]
        results = net_class.one('LengthResults')
        row = results.one('Rules/Rule')
        self.assertEqual((main['Name'], main['FixedLength'], main['Delta']), ('Y', -1, Decimal('7.62')))
        self.assertEqual((net_class['FixedLength'], net_class['LengthDelta'], row['Length']),
                         (15, Decimal('1.2'), Decimal('3.9')))
        self.assertEqual(document.one('/Board/LengthRules').children(), [])
        for name in ('Name', 'FixedLength', 'Delta', 'NetClass', 'Type'):
            self.assertIsNone(results.child(name))
        self.assertIs(row['Net'], result.routing.core.nets[7])
        self.assertIs(row['Pad1'], result.routing.core.pads[8, 1])
        self.assertIs(row['Pad2'], result.routing.core.pads[8, 2])
        self.assertTrue(row['Error'])
        document.references.validate()

    def test_xml_missing_optional_policy_settings_use_loader_defaults(self):
        result = assemble_rules(prepared(xml_source().replace('MainLengthRule Type="By User"', 'MainLengthRule')))
        main = result.document.one('/Board/MainLengthRule')
        self.assertFalse(main['AnyError'])
        self.assertNotIn('Type', main.schema.fields)
        self.assertIsNone(main['Class'])
        self.assertEqual(main.one('Rules').children(), [])

    def test_user_rules_keep_independent_settings_and_ignore_unused_class_selection(self):
        text = xml_source().replace('Type="By NetClass"', 'Type="By User"').replace(
            'AnyError="Y" NetClass="70"', 'AnyError="Y" NetClass="999"')
        result = assemble_rules(prepared(text))
        policy = result.document.one('/Board/LengthRules/LengthRule')
        self.assertEqual((policy['Name'], policy['FixedLength'], policy['Delta']),
                         ('Signals', 6, Decimal('.9')))
        self.assertIsNone(result.classes[1].child('LengthResults'))
        self.assertIsNone(policy.child('NetClass'))

    def test_inactive_class_results_are_removed_without_changing_authored_class_settings(self):
        result = assemble_rules(prepared(xml_source().replace('CheckLength="Y"', 'CheckLength="N"')))
        net_class = result.classes[1]
        self.assertFalse(net_class['CheckLength'])
        self.assertEqual(net_class['FixedLength'], 15)
        self.assertIsNone(net_class.child('LengthResults'))
        self.assertEqual(result.document.one('/Board/LengthRules').children(), [])

    def test_last_result_for_a_class_survives_normalization_without_duplicate_policy_values(self):
        text = xml_source()
        rule = XML.split('<LengthRules>')[1].split('</LengthRules>')[0]
        text = text.replace('</LengthRules>', rule.replace('Length="1.3"', 'Length="2.5"')+'</LengthRules>')
        result = assemble_rules(prepared(text))
        results = result.classes[1].children('LengthResults')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].one('Rules/Rule')['Length'], Decimal('7.5'))
        result.document.references.validate()

    def test_bad_rows_enums_keys_and_mixed_net_targets_fail(self):
        for text in (asc_source().replace('7.62 "N" "Y" -1 0', '7.62 "N" "Y" -1 2'),
                     asc_source().replace('73 17 9 17 11 3.5', '74 17 9 17 11 3.5')):
            with self.subTest(format='asc'), self.assertRaises((PcbError, ValueError)):
                assemble_rules(prepare_core(text))
        for before, after in (('By NetClass', 'Unknown'), ('NetClass="70"', 'NetClass="71"'),
                              ('NetId="7" Comp1', 'NetId="999" Comp1')):
            with self.subTest(after=after), self.assertRaises((PcbError, ValueError)):
                assemble_rules(prepared(xml_source().replace(before, after)))

    def test_missing_positive_pad_targets_compact_rows_and_report_import_normalization(self):
        @import_diagnostics('asc')
        def read_asc(text):
            return assemble_rules(prepare_core(text)).document

        @import_diagnostics('dipxml')
        def read_xml(text):
            return assemble_rules(prepared(text)).document

        for text in (asc_source().replace('73 17 9 17 11 3.5', '73 17 99 17 11 3.5'),
                     asc_source().replace('73 17 9 17 11 3.5', '73 17 9 -1 11 3.5')):
            report = ConversionReport()
            document = read_asc(text, report=report)
            self.assertEqual(document.one('/Board/MainLengthRule/Rules').children(), [])
            self.assertEqual(len(document.select('/Board/NetClasses/NetClass[2]/LengthResults/Rules/Rule')), 1)
            self.assertEqual([notice.rule for notice in report.infos if notice.rule != 'footprint-frame-normalization'],
                             ['stale-length-connections'])
            self.assertFalse(report.errors)
            # The enclosing draft assembly still reports its incomplete scope.
            self.assertEqual([notice.rule for notice in report.warnings], ['import-diagnostic'])
            document.references.validate()
        for before, after in (('Pad1="17"', 'Pad1="99"'), ('Comp1="8"', 'Comp1="800"')):
            report = ConversionReport()
            document = read_xml(xml_source().replace(before, after), report=report)
            self.assertEqual(document.one('/Board/NetClasses/NetClass[2]/LengthResults/Rules').children(), [])
            self.assertEqual([notice.rule for notice in report.infos if notice.rule != 'footprint-frame-normalization'],
                             ['stale-length-connections'])
            document.references.validate()

    def test_nonpositive_pad_selectors_have_no_endpoint_or_unused_component_reference(self):
        for selector in ('17 -1', '999 0', '-1 -2'):
            result = assemble_rules(prepare_core(asc_source().replace('73 17 9 17 11 3.5',
                                                                         '73 '+selector+' 17 11 3.5')))
            row = result.document.one('/Board/MainLengthRule/Rules/Rule')
            self.assertIsNone(row['Pad1'])
            self.assertIsNone(row['Component1'])
            self.assertIs(row['Pad2'], result.routing.core.pads[17, 11])
        result = assemble_rules(prepared(xml_source().replace('Comp1="8" Pad1="17"', 'Comp1="999" Pad1="0"')))
        row = result.classes[1].one('LengthResults/Rules/Rule')
        self.assertIsNone(row['Pad1'])
        self.assertIs(row['Pad2'], result.routing.core.pads[8, 2])

    def test_class_results_for_nets_that_changed_class_are_modernized_with_a_report(self):
        @import_diagnostics('dipxml')
        def read(text):
            return assemble_rules(prepared(text)).document
        text = xml_source().replace('Net Id="7" NetClass="70"', 'Net Id="7" NetClass="4"')
        report = ConversionReport()
        document = read(text, report=report)
        results = document.one('/Board/NetClasses/NetClass[2]/LengthResults')
        self.assertEqual(results.one('Rules').children(), [])
        self.assertFalse(results['AnyError'])
        self.assertEqual([notice.rule for notice in report.infos if notice.rule != 'footprint-frame-normalization'],
                         ['stale-class-length-connections'])
        document.references.validate()


if __name__ == '__main__':
    unittest.main()
