"""Pour state is independent of optional fill, and export never changes either."""
from decimal import Decimal
import unittest

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.common.units import XmlUnits
from lib.pcb.formats.dipxml.pour_output import project_pours
from lib.pcb.formats.dipxml.syntax import dumps
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_cache_projection import signature
from lib.pcb.tests.test_dipxml_graphics import source
from lib.pcb.tests.test_dipxml_library import read
from lib.pcb.tests.test_xml_component_output import context
from lib.pcb.tests.test_xml_routing_output import with_component_library


POUR = '/Board/CopperPours/CopperPour'


def design():
    return read(with_component_library(source()), report=ConversionReport())


def reopen(document, *, units='mm', report=None):
    output, _ = context(document, units=units, report=report)
    output.one('/Source/Board').append(project_pours(document.one('/Board'), units=XmlUnits(units), report=report))
    return read(dumps(output), report=ConversionReport()), output


class XmlPourOutputTests(unittest.TestCase):
    def test_filled_without_fill_retains_its_authored_choice_and_physical_values(self):
        document = design()
        pour = document.one(POUR)
        pour['ShieldGroup'], pour['TraceShieldGroup'] = 0, 7
        expected = signature(pour)
        before = model_text(document, preserve=False)
        for units in ('mm', 'mil', 'inch'):
            current = document
            for _ in range(3):
                report = ConversionReport()
                current, output = reopen(current, units=units, report=report)
                actual = current.one(POUR)
                values = signature(actual)
                self.assertEqual(values.keys(), expected.keys())
                for name, value in expected.items():
                    if isinstance(value, (int, Decimal)) and not isinstance(value, bool):
                        self.assertLessEqual(abs(values[name]-value), Decimal('1e-23'), name)
                    else:
                        self.assertEqual(values[name], value, name)
                self.assertTrue(actual['Poured'])
                self.assertIsNone(actual.child('Fill'))
                self.assertNotIn('pour-fill-recalculation', {notice.rule for notice in report.notices})
                self.assertIsNone(output.one('/Source/Board/CopperPours/CopperPour').child('RegionsDone'))
                current.references.validate()
        self.assertEqual(model_text(document, preserve=False), before)

    def test_supplied_fill_is_omitted_with_info_without_changing_poured_or_source(self):
        for poured in (False, True):
            with self.subTest(poured=poured):
                document = design()
                pour = document.one(POUR)
                pour['Poured'] = poured
                fill = pour.add('Fill')
                region = fill.add('Regions').add('Region', 5)
                line = fill.add('Lines').add('Line')
                for name, value in dict(X1=1, Y1=2, X2=3, Y2=4, Region=region).items():
                    line[name] = value
                before, report = model_text(document, preserve=False), ConversionReport()
                rebuilt, _ = reopen(document, report=report)
                self.assertEqual(rebuilt.one(POUR)['Poured'], poured)
                self.assertIsNone(rebuilt.one(POUR).child('Fill'))
                self.assertIn('pour-fill-recalculation', {notice.rule for notice in report.infos})
                self.assertEqual(report.warnings, [])
                self.assertEqual(model_text(document, preserve=False), before)

    def test_layer_and_net_reordering_uses_current_targets(self):
        document = design()
        pour = document.one(POUR)
        layer, net = pour['Layer'], pour['Net']
        layer.move_to(layer.parent, 2)
        net['Name'] = 'New name'
        rebuilt, _ = reopen(document)
        actual = rebuilt.one(POUR)
        self.assertEqual(actual['Lay'], 2)
        self.assertEqual(actual['Net']['Name'], 'New name')
        self.assertEqual(actual['Layer']['Name'], layer['Name'])

    def test_invalid_output_is_rejected_without_modifying_the_source(self):
        for invalid in ('layer', 'area', 'unknown'):
            with self.subTest(invalid=invalid):
                document = design()
                pour = document.one(POUR)
                if invalid == 'layer':
                    pour['Layer'] = None
                elif invalid == 'area':
                    pour['MinimumArea'] = -1
                else:
                    pour.add('UnmappedPourData', 9)
                before = model_text(document, preserve=False)
                with self.assertRaises(PcbError):
                    reopen(document)
                self.assertEqual(model_text(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
