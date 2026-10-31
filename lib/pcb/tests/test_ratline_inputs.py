"""Compact ASC and named XML ratlines share one current PCB record."""
from decimal import Decimal
import unittest

from lib.common.asc import loads, dumps
from lib.common.conversion import ConversionReport, import_diagnostics
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.tests.test_asc_core import fixture as asc_fixture
from lib.pcb.tests.test_dipxml_classes import source as xml_fixture
from lib.pcb.tests.test_dipxml_electrical import prepared


XML = '''<Ratlines><Ratline Id="17" Hidden="Y" X1="1" Y1="2" X2="3" Y2="4"
          Comp1="8" Pad1="17" Comp2="8" Pad2="41"/></Ratlines>'''


def asc_source():
    data = loads(asc_fixture())
    data.one('/Board').add('Connections').add('Connection', 'Y', 1, 2, 3, 4, 17, 17, 9, 11, 'Y')
    return dumps(data, preserve=False)


def xml_source():
    return xml_fixture().replace('</Board>', XML+'</Board>')


class RatlineInputTests(unittest.TestCase):
    def test_ascii_compact_columns_have_named_geometry_and_hidden_state(self):
        result = assemble_core(prepare_core(asc_source()))
        row = result.document.one('/Board/Ratlines/Ratline')
        self.assertTrue(row['Hidden'])
        self.assertEqual((row['X1'], row['Y1'], row['X2'], row['Y2']), (1, 2, 3, 4))
        self.assertIs(row['Pad1'], result.pads[17, 9])
        self.assertIs(row['Pad2'], result.pads[17, 11])
        result.document.references.validate()

    def test_xml_axes_lengths_and_nonconsecutive_keys_are_consumed(self):
        result = assemble_core(prepared(xml_source()))
        row = result.document.one('/Board/Ratlines/Ratline')
        self.assertTrue(row['Hidden'])
        self.assertEqual((row['Id'], row['X1'], row['Y1'], row['Y2']), (0, 3, -6, -12))
        self.assertIs(row['Pad1'], result.pads[8, 1])
        self.assertIs(row['Pad2'], result.pads[8, 2])
        other = assemble_core(prepared(xml_source().replace('Units="mm"', 'Units="mil"')))
        self.assertEqual(other.document.one('/Board/Ratlines/Ratline')['X1'], Decimal('.0762'))

    def test_missing_flags_use_reset_defaults_and_counter_ids_do_not_select_targets(self):
        text = xml_source().replace('<Ratline Id="17" Hidden="Y"', '<Ratline Id="99"')
        row = assemble_core(prepared(text)).document.one('/Board/Ratlines/Ratline')
        self.assertFalse(row['Hidden'])
        self.assertTrue(row['Enabled'])
        self.assertEqual(row['PadIndex1'], 0)

    def test_missing_positive_xml_pad_is_reported_as_an_import_repair(self):
        @import_diagnostics('dipxml')
        def read(text):
            return assemble_core(prepared(text)).document
        report = ConversionReport()
        document = read(xml_source().replace('Pad1="17"', 'Pad1="99"'), report=report)
        self.assertEqual(document.one('/Board/Ratlines').children(), [])
        self.assertTrue(any(n.rule == 'stale-ratlines' for n in report.infos))
        self.assertFalse(report.errors)

    def test_invalid_compact_records_and_xml_field_types_are_explicit(self):
        for text in (asc_source().replace('17 17 9 11', '17 17 9.5 11'),
                     asc_source().replace('"Y" 1 2 3 4', '"invalid" 1 2 3 4')):
            with self.assertRaises(ValueError):
                assemble_core(prepare_core(text))
        with self.assertRaises(ValueError):
            assemble_core(prepared(xml_source().replace('Hidden="Y"', 'Hidden="invalid"')))


if __name__ == '__main__':
    unittest.main()
