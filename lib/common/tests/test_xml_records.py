"""Strict XML records distinguish attribute and element namespaces."""
import unittest
from decimal import Decimal, ROUND_DOWN, localcontext

from lib.common.xml import XmlDialect, loads
from lib.common.xml_records import XmlRecord, area, length
from lib.common.units import XmlUnits


class XmlRecordTests(unittest.TestCase):
    def test_lengths_keep_long_values_and_reverse_axes_without_ambient_rounding(self):
        value = Decimal('12345678901234567890.12345678901234567890123456789')
        expected = Decimal('37037036703703703670.37037036703703703670370370367')
        with localcontext() as context:
            context.prec, context.rounding = 3, ROUND_DOWN
            self.assertEqual(length(value, XmlUnits('mm')).value, expected)
            self.assertEqual(length(value, XmlUnits('mm'), reverse=True).value, expected.copy_negate())
        with self.assertRaises(ValueError):
            length('4', XmlUnits('mm'))

    def test_area_uses_a_squared_unit_scale_without_squaring_the_authored_value(self):
        self.assertEqual(area(4, XmlUnits('mm')).value, 36)
        self.assertEqual(area(4, XmlUnits('mil')).value, Decimal('.02322576'))
        with localcontext() as context:
            context.prec = 3
            self.assertEqual(area(Decimal('1.234567890123456789'), XmlUnits('mm')).value,
                             Decimal('11.11111101111111110100'))
        with self.assertRaises(ValueError):
            area('4', XmlUnits('mm'))

    def record(self, text):
        dialect = XmlDialect(number_attributes=frozenset({('Item', 'Name')}))
        return XmlRecord(loads('<Source>'+text+'</Source>', dialect=dialect).one('/Source/Item'))

    def test_shared_name_has_independent_attribute_identity_and_element_text(self):
        record = self.record('<Item Name="17"><Name>Display text</Name></Item>')
        self.assertTrue(record.has('Name', attribute=True))
        self.assertTrue(record.has('Name', attribute=False))
        with self.assertRaisesRegex(ValueError, 'expected one Name'):
            record.text('Name')
        self.assertEqual(record.integer('Name', attribute=True), 17)
        self.assertEqual(record.text('Name', attribute=False), 'Display text')
        record.finish()

    def test_defaults_and_strict_consumption_keep_the_namespaces_separate(self):
        record = self.record('<Item Name="17"/>')
        self.assertFalse(record.has('Name', attribute=False))
        self.assertEqual(record.text('Name', 'Default', attribute=False), 'Default')
        with self.assertRaisesRegex(ValueError, 'unsupported XML fields'):
            record.finish()
        self.assertEqual(record.integer('Name', attribute=True), 17)
        record.finish()

    def test_duplicate_elements_and_fractional_integer_still_fail(self):
        record = self.record('<Item Name="1.5"><Name>A</Name><Name>B</Name></Item>')
        with self.assertRaisesRegex(ValueError, 'integer'):
            record.integer('Name', attribute=True)
        with self.assertRaisesRegex(ValueError, 'expected one Name'):
            record.text('Name', attribute=False)

    def test_empty_record_allows_indentation_but_rejects_meaningful_text(self):
        self.record('<Item>\n\t </Item>').finish()
        for text in ('text', '0', ' N ', '\u00a0'):
            with self.subTest(text=text):
                record = self.record('<Item>'+text+'</Item>')
                with self.assertRaisesRegex(ValueError, 'unexpected XML text'):
                    record.finish()
        record = self.record('<Item><Name>  </Name></Item>')
        self.assertEqual(record.text('Name'), '  ')
        record.finish()


if __name__ == '__main__':
    unittest.main()
