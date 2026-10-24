"""Public XML units and Y direction, using explicit physical lengths."""
from decimal import Decimal
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib import Value
from lib.schematic.formats.dchxml.units import (DchXmlUnits)
from lib.schematic.formats.asc.policy import (number_text)


class DchXmlUnitsTests(unittest.TestCase):
    def test_component_and_footprint_lengths(self):
        units = DchXmlUnits('mil')
        self.assertEqual(tuple(map(number_text, units.point(Decimal('-41.91'), Decimal('-38.1')))), ('-550', '500'))
        self.assertEqual(number_text(units.length(Decimal('5.52'))), '72.4409')
        self.assertEqual(number_text(units.length(Decimal('-0.03'))), '-0.3937')
        for name, size in (('mm', 3), ('mil', .0762), ('inch', 76.2)):
            unit = DchXmlUnits(name)
            self.assertEqual(tuple(map(number_text, unit.point(size, -2*size))), ('1', '2'))
            self.assertEqual(unit.internal_point(1, 2), (Decimal(str(size)), -2*Decimal(str(size))))

    def test_current_value_and_invalid_values_are_explicit(self):
        unit = DchXmlUnits('mm')
        value = Value.of(Decimal('3.00015'))
        self.assertEqual(unit.length(value), Decimal('1.00005'))
        self.assertEqual(unit.internal_length(unit.length(value)), value.value)
        for invalid in (True, '3', Value.of(3, unit='%')):
            with self.subTest(value=invalid), self.assertRaises((TypeError, ValueError)):
                unit.length(invalid)
        for invalid in (float('inf'), Decimal('NaN')):
            with self.assertRaises(ValueError):
                unit.length(invalid)
        with self.assertRaises(ValueError):
            DchXmlUnits('in')


if __name__ == '__main__':
    unittest.main()
