"""Current XML check rules retain physical dimensions and class/layer targets."""
from decimal import Decimal
import unittest

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.common.units import XmlUnits
from lib.pcb.formats.dipxml.output_keys import OutputKeys
from lib.pcb.formats.dipxml.rule_output import project_design_rules
from lib.pcb.formats.dipxml.syntax import dumps
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_cache_projection import signature
from lib.pcb.tests.test_dipxml_design_rules import source
from lib.pcb.tests.test_dipxml_library import read
from lib.pcb.tests.test_xml_routing_output import context, with_component_library


def design(text=None):
    return read(with_component_library(source() if text is None else text), report=ConversionReport())


def reopen(document, *, units='mm', report=None):
    output, library = context(document, units=units, report=report)
    board, target = document.one('/Board'), output.one('/Source/Board')
    rules = project_design_rules(board, keys=OutputKeys(board, library), units=XmlUnits(units), report=report)
    for section in tuple(rules.children()):
        section.move_to(target)
    return read(dumps(output), report=ConversionReport()), output


class XmlRuleOutputTests(unittest.TestCase):
    def assert_facts(self, actual, expected):
        self.assertEqual(actual.keys(), expected.keys())
        for name, value in expected.items():
            if isinstance(value, (int, Decimal)) and not isinstance(value, bool):
                self.assertLessEqual(abs(actual[name]-value), Decimal('1e-23'), name)
            else:
                self.assertEqual(actual[name], value, name)

    def test_class_pairs_checks_and_material_stack_survive_units_and_repeated_output(self):
        document = design()
        expected = {name: signature(document.one('/Board/'+name)) for name in ('ClassClearances', 'DRC', 'LayerStackItems')}
        before = model_text(document, preserve=False)
        for units in ('mm', 'mil', 'inch'):
            current = document
            for _ in range(3):
                current, _ = reopen(current, units=units)
                for name, values in expected.items():
                    self.assert_facts(signature(current.one('/Board/'+name)), values)
                self.assertTrue(current.one('/Board')['ClassToClass'])
                self.assertEqual(current.one('/Board')['LayerStackName'], document.one('/Board')['LayerStackName'])
                current.references.validate()
        self.assertEqual(model_text(document, preserve=False), before)

    def test_per_layer_rules_follow_reordered_copper_layers(self):
        document = design()
        last = document.one('/Board/Layers/Layer[3]')
        last.move_to(last.parent, 1)
        current, _ = reopen(document)
        for source in document.select('/Board/DRC/LayClearances/LayClearance'):
            # Collection order itself is projected in stack order, so match the
            # independently named target when comparing each authored rule.
            result = next(row for row in current.select('/Board/DRC/LayClearances/LayClearance')
                          if row['Layer']['Name'] == source['Layer']['Name'])
            self.assertEqual(result['SameSmdToVia'], source['SameSmdToVia'])
            self.assertEqual(result['Lay'], source['Lay'])
        current.references.validate()

    def test_uniform_previous_rules_have_no_layer_identity_and_ui_state_is_separate(self):
        last = '''<LastDRC AllLayers="Y"><Name>Previous</Name><LayClearances><LayClearance Lay="0">
          <ClearanceDetails TraceToVia=".7"/></LayClearance></LayClearances>
          <LaySizes><LaySize Lay="0" MinTrace=".1"/></LaySizes></LastDRC>'''
        document = design(source().replace('</Board>', last+'</Board>'))
        previous = document.one('/Board/LastDRC')
        previous['ShowList'], previous['RealTimeMode'] = True, 2
        report, before = ConversionReport(), model_text(document, preserve=False)
        current, _ = reopen(document, units='mil', report=report)
        previous = current.one('/Board/LastDRC')
        self.assertIsNone(previous.one('LayClearances/LayClearance')['Layer'])
        self.assertEqual(previous.one('LayClearances/LayClearance/ClearanceDetails')['TraceToVia'], Decimal('2.1'))
        self.assertIsNone(previous.child('ShowList'))
        self.assertIn('previous-check-ui', {notice.rule for notice in report.infos})
        self.assertEqual(model_text(document, preserve=False), before)

    def test_empty_optional_check_rows_remain_valid(self):
        # A separate optional snapshot can legitimately have no layer rows.
        document = design(source().replace('</Board>', '<LastDRC AllLayers="N"/></Board>'))
        current, _ = reopen(document)
        self.assertFalse(current.one('/Board/LastDRC/LayClearances').children())

    def test_class_pair_targets_survive_class_reordering_and_renaming(self):
        document = design()
        last = document.one('/Board/NetClasses/NetClass[2]')
        last['Name'] = 'Power'
        last.move_to(last.parent, 0)

        def pairs(current):
            return {tuple(sorted((cell['Class1']['Name'], cell['Class2']['Name']))):
                    (cell['AllLayers'], cell.get('Clearance'),
                     {row['Layer']['Name']: row['Clearance'] for row in cell.select('LayerClearances/LayerClearance')})
                    for cell in current.select('/Board/ClassClearances/Cell')}

        report = ConversionReport()
        current, _ = reopen(document, report=report)
        self.assertEqual(pairs(current), pairs(document))
        self.assertEqual(current.one('/Board')['DefaultClass']['Name'], document.one('/Board')['DefaultClass']['Name'])
        self.assertIn('default-class-position', {notice.rule for notice in report.infos})
        current.references.validate()

    def test_unknown_rule_data_is_an_atomic_output_error(self):
        document = design()
        document.one('/Board/DRC/LaySizes/LaySize[1]').add('UnmappedRule', 3)
        before = model_text(document, preserve=False)
        with self.assertRaises(PcbError):
            reopen(document)
        self.assertEqual(model_text(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
