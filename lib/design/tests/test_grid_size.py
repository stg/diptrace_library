"""One editable grid spacing, with generated destination precision fields."""
from decimal import Decimal
import unittest

from lib.design import new_schematic, parse


class GridSizeTests(unittest.TestCase):
    def test_all_formats_use_one_current_spacing(self):
        for format in ('dch', 'asc', 'dchxml'):
            with self.subTest(format=format):
                source = new_schematic()
                source.one('/Schematic/Settings/GridSize').set_values(Decimal('.125'))
                loaded = parse(getattr(source, 'to_'+format+'_bytes')(), format=format)
                self.assertEqual(loaded.one('/Schematic/Settings').scalar('GridSize'), Decimal('.125'))
                self.assertFalse(loaded.select('//GridNumerator'))
                self.assertFalse(loaded.select('//GridDivisor'))

    def test_fractional_binary_grid_stabilizes_and_remains_editable(self):
        document = new_schematic()
        document.one('/Schematic/Settings/GridSize').set_values(Decimal(1)/3)
        encoded = document.to_dch_bytes()
        for _ in range(3):
            loaded = parse(encoded, format='dch')
            self.assertEqual(loaded.one('/Schematic/Settings').scalar('GridSize'), Decimal(1)/3)
            self.assertEqual(loaded.to_dch_bytes(), encoded)
            encoded = loaded.to_dch_bytes()
        loaded.one('/Schematic/Settings/GridSize').set_values(Decimal('.125'))
        edited = parse(loaded.to_dch_bytes(), format='dch')
        self.assertEqual(edited.one('/Schematic/Settings').scalar('GridSize'), Decimal('.125'))
        self.assertEqual(document.one('/Schematic/Settings').scalar('GridSize'), Decimal(1)/3)

    def test_binary_fraction_keeps_spacing_below_the_scalar_quantum(self):
        document = new_schematic()
        document.one('/Schematic/Settings/GridSize').set_values(Decimal('.0000125'))
        encoded = document.to_dch_bytes()
        loaded = parse(encoded, format='dch')
        self.assertEqual(loaded.one('/Schematic/Settings').scalar('GridSize'), Decimal('.0000125'))
        self.assertEqual(loaded.to_dch_bytes(), encoded)


if __name__ == '__main__':
    unittest.main()
