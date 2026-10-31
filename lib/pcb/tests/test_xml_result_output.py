"""XML check snapshots keep measurements while selectors follow current targets."""
from decimal import Decimal
import unittest
from xml.etree import ElementTree

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.common.units import XmlUnits
from lib.pcb.formats.dipxml.graphic_output import project_outline, project_drawings
from lib.pcb.formats.dipxml.output_keys import OutputKeys
from lib.pcb.formats.dipxml.result_output import project_results
from lib.pcb.formats.dipxml.syntax import dumps
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_cache_projection import signature
from lib.pcb.tests.test_dipxml_library import read
from lib.pcb.tests.test_drc_result_inputs import xml_source
from lib.pcb.tests.test_xml_routing_output import context, with_component_library


def design(text=None):
    return read(with_component_library(xml_source() if text is None else text), report=ConversionReport())


def reopen(document, *, units='mm', report=None):
    output, library = context(document, units=units, report=report)
    board, target, scale = document.one('/Board'), output.one('/Source/Board'), XmlUnits(units)
    target.append(project_outline(board, units=scale))
    target.append(project_drawings(board, units=scale, report=report))
    target.append(project_results(board, keys=OutputKeys(board, library), units=scale, report=report))
    return read(dumps(output), report=ConversionReport()), output


class XmlResultOutputTests(unittest.TestCase):
    def assert_facts(self, actual, expected):
        self.assertEqual(actual.keys(), expected.keys())
        for name, value in expected.items():
            if isinstance(value, (int, Decimal)) and not isinstance(value, bool):
                self.assertLessEqual(abs(actual[name]-value), Decimal('1e-23'), name)
            else:
                self.assertEqual(actual[name], value, name)

    def test_supplied_results_survive_units_and_repeated_output_without_recalculation(self):
        document = design()
        expected, before = signature(document.one('/Board/DesignErrors')), model_text(document, preserve=False)
        for units in ('mm', 'mil', 'inch'):
            current = document
            for _ in range(3):
                current, _ = reopen(current, units=units)
                self.assert_facts(signature(current.one('/Board/DesignErrors')), expected)
                current.references.validate()
        self.assertEqual(model_text(document, preserve=False), before)

    def test_pad_point_and_component_reorders_keep_the_selected_objects(self):
        document = design()
        source = document.one('/Board/DesignErrors/DesignError')
        pad, point = source['Target1'], source['Target2']
        pad.move_to(pad.parent, 1)
        point.move_to(point.parent, 0)
        component = document.one('/Board/Components/Component')
        document.copy(component, parent=component.parent, index=0, fields={'RefDes': 'U2'})
        expected = signature(document.one('/Board/DesignErrors'))
        current, _ = reopen(document)
        self.assert_facts(signature(current.one('/Board/DesignErrors')), expected)
        result = current.one('/Board/DesignErrors/DesignError')
        self.assertIs(result['Target1'], current.one('/Board/Components/Component[2]/Pattern/Pads/Pad[2]'))
        self.assertIs(result['Target2'], current.one('/Board/Nets/Net/Traces/Trace[1]/Points/Point[1]'))
        current.references.validate()

    def test_ambiguous_display_label_uses_a_numeric_spelling_to_retain_the_distinct_type(self):
        document = design()
        error = document.one('/Board/DesignErrors/DesignError')
        for kind, spelling in ((10, 'TraceLength'), (11, '11')):
            error['Type'] = kind
            current, output = reopen(document)
            self.assertEqual(current.one('/Board/DesignErrors/DesignError')['Type'], kind)
            node = ElementTree.fromstring(dumps(output)).find('./Board/DesignErrors/DesignError')
            self.assertEqual(node.get('Type'), spelling)

    def test_unavailable_point_remains_unresolved_and_warns(self):
        document = design(xml_source().replace('Point2="1"', 'Point2="99"'))
        expected = document.one('/Board/DesignErrors/DesignError/UnresolvedTarget2').values
        before, report = model_text(document, preserve=False), ConversionReport()
        current, _ = reopen(document, report=report)
        self.assertEqual(current.one('/Board/DesignErrors/DesignError/UnresolvedTarget2').values, expected)
        self.assertIn('unresolved-design-error-targets', {notice.rule for notice in report.warnings})
        self.assertEqual(model_text(document, preserve=False), before)

    def test_unknown_result_data_fails_without_modifying_source(self):
        for invalid in ('unknown', 'inactive'):
            with self.subTest(invalid=invalid):
                document = design()
                error = document.one('/Board/DesignErrors/DesignError')
                if invalid == 'unknown':
                    error.add('UnmappedMeasurement', 3)
                else:
                    error['Enabled'] = False
                before = model_text(document, preserve=False)
                with self.assertRaises(PcbError):
                    reopen(document)
                self.assertEqual(model_text(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
