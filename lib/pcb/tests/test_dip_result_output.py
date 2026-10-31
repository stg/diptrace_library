"""Binary saved checks retain measurements and track current object identities."""
from decimal import Decimal
import unittest

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.pcb.formats.asc.graphic_projection import project_graphics
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_component_projection import signature
from lib.pcb.tests.test_pair_projection import syntax
from lib.pcb.tests.test_dip_pair_output import sections, read_sections, reopen, with_rules
from lib.pcb.tests.test_result_projection import design
from lib.pcb.tests.test_drc_length_targets import read as read_length, source as length_source, error as length_error


def result_source(document):
    source = syntax(document, report=ConversionReport())
    for row in tuple(project_graphics(document.one('/Board'), report=ConversionReport()).children()):
        row.move_to(source.one('/Board'))
    return source


class DipResultOutputTests(unittest.TestCase):
    def test_target_domains_measurements_and_current_rules_reopen_unchanged(self):
        document = with_rules(design())
        drc = document.one('/Board/DRC')
        drc['RealTimeMode'], drc['DRCDone'] = 2, True
        before = dumps(document, preserve=False)
        expected = signature(document.one('/Board/DesignErrors'))
        raw, _, _, _ = read_sections(document)
        self.assertEqual((raw.one('DRC')['RealTimeMode'], raw.one('DRC')['DRCDone']), (2, True))
        saved = raw.one('DesignErrors/DesignError[1]')
        self.assertEqual((saved['Value'], saved['Rule']), (Decimal('.1'), Decimal('.2')))
        rebuilt = reopen(document, source=result_source(document))
        self.assertEqual(signature(rebuilt.one('/Board/DesignErrors')), expected)
        self.assertEqual(signature(reopen(rebuilt, source=result_source(rebuilt)).one('/Board/DesignErrors')), expected)
        self.assertEqual(dumps(document, preserve=False), before)
        rebuilt.references.validate()

    def test_reordering_targets_and_layers_updates_boundary_offsets_and_masks(self):
        document = with_rules(design())
        board = document.one('/Board')
        board.one('Components/Component/Pattern/Pads/Pad[1]').move_to(board.one('Components/Component/Pattern/Pads'))
        board.one('Nets/Net/Traces/Trace/Points/Point[2]').move_to(board.one('Nets/Net/Traces/Trace/Points'))
        board.one('Layers/Layer[2]').move_to(board.one('Layers'), 0)
        raw, _, _, _ = read_sections(document)
        self.assertEqual(raw.one('DesignErrors/DesignError[1]')['SubObject1'], 2)
        self.assertEqual(raw.one('DesignErrors/DesignError[2]')['SubObject1'], 1)
        self.assertEqual(raw.one('DesignErrors/DesignError[3]')['Point1'], 2)
        first = raw.one('DesignErrors/DesignError[1]')
        self.assertEqual(first['RuleLay'], 0)
        self.assertEqual([item.values for item in first.select('Lays/Item')], [(True,), (False,)])
        rebuilt = reopen(document, source=result_source(document))
        self.assertEqual(signature(rebuilt.one('/Board/DesignErrors')), signature(board.one('DesignErrors')))

    def test_unresolved_objects_classes_and_layers_are_explicit_and_reported(self):
        document = with_rules(design(unresolved=True))
        report = ConversionReport()
        raw, _, _, _ = read_sections(document, report=report)
        first = raw.one('DesignErrors/DesignError[1]')
        self.assertEqual((first['Object2'], first['RuleLay'], first['ObjectNetClass2']), (999, 99, 99))
        self.assertEqual(len(first.select('Lays/Item')), 100)
        self.assertEqual(first.one('Lays/Item[100]').values, (True,))
        self.assertEqual({notice.rule for notice in report.warnings},
                         {'unresolved-design-error-targets', 'unresolved-design-error-layer',
                          'unresolved-design-error-class'})
        rebuilt = reopen(document, report=ConversionReport(), source=result_source(document))
        current = rebuilt.one('/Board/DesignErrors/DesignError[1]')
        self.assertEqual(current.one('UnresolvedTarget2').values, (999, -1, -1, -1))
        self.assertEqual((current['UnresolvedObjectNetClass2'], current['UnresolvedRuleLay']), (99, 99))
        self.assertEqual([row['Index'] for row in current.select('Layers/Layer')], [1, 99])

    def test_detached_outline_check_does_not_regain_an_object_target(self):
        document = with_rules(design())
        for row in document.select('/Board/DesignErrors/DesignError'):
            row['Target1'], row['Target2'] = None, None
        report = ConversionReport()
        rebuilt = reopen(document, report=report, source=result_source(document))
        self.assertEqual(report.warnings, [])
        self.assertIn('detached-outline-check', [notice.rule for notice in report.infos])
        self.assertTrue(all(row['Target1'] is None and row['Target2'] is None
                            for row in rebuilt.select('/Board/DesignErrors/DesignError')))
        self.assertEqual(document.one('/Board/DesignErrors/DesignError[5]')['ObjectType1'], 1)

    def test_class_selected_default_reorders_length_targets_and_class_selectors_together(self):
        document = with_rules(read_length(length_source(length_error(0), length_error(1)), report=ConversionReport()))
        board = document.one('/Board')
        first, second = board.select('NetClasses/NetClass')
        first['CheckLength'] = True
        board['DefaultClass'] = second
        row = board.one('DesignErrors/DesignError[2]')
        row['NetClass1'] = second
        raw, _, _, _ = read_sections(document)
        saved = raw.one('DesignErrors/DesignError[2]')
        self.assertEqual((saved['Object1'], saved['ObjectNetClass1']), (0, 0))
        rebuilt = reopen(document, source=result_source(document))
        current = rebuilt.one('/Board/DesignErrors/DesignError[2]')
        self.assertEqual(current['NetClass1']['Name'], second['Name'])
        self.assertEqual(current['Target1'].parent.parent.parent['Name'], second['Name'])
        self.assertEqual((current['Value'], current['Rule']), (row['Value'], row['Rule']))

    def test_unmapped_results_and_target_domains_fail_without_mutation(self):
        for unknown in (True, False):
            document = with_rules(design())
            row = document.one('/Board/DesignErrors/DesignError[1]')
            if unknown:
                row.add('Unmapped', 12)
            else:
                row['Target1'] = None
                row['ObjectType1'] = 28
            before = dumps(document, preserve=False)
            with self.subTest(unknown=unknown), self.assertRaises(PcbError):
                sections(document)
            self.assertEqual(dumps(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
