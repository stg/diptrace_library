"""XML symbol output reports verification-state omissions without losing content."""
import unittest

from lib.common.conversion import ConversionReport
from lib.common.symbol_objects import new_symbol
from lib.common.units import XmlUnits
from lib.common.xml_symbol_output import project_symbol


class XmlSymbolVerificationTests(unittest.TestCase):
    def test_saved_states_warn_in_each_family_without_mutating_the_symbol(self):
        for destination in ('dchxml', 'dipxml'):
            with self.subTest(destination=destination):
                part = new_symbol('Device', 'U')
                states = (True, False, True, False, False, True, False)
                part['Verification'] = states
                report = ConversionReport()
                output = project_symbol(part, units=XmlUnits('mm'), destination=destination, report=report)
                self.assertEqual(output.scalar('Name'), 'Device')
                self.assertIsNone(output.child('Verification'))
                self.assertEqual(part['Verification'], states)
                self.assertEqual([notice.rule for notice in report.warnings], ['symbol-verification'])
                self.assertEqual(report.warnings[0].format, destination)

    def test_default_states_need_no_omission_notice(self):
        report = ConversionReport()
        project_symbol(new_symbol(), units=XmlUnits('mm'), destination='dipxml', report=report)
        self.assertEqual(report.notices, [])


if __name__ == '__main__':
    unittest.main()
