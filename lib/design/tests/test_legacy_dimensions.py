"""Selection bounds and unplaced definition geometry have different minima."""
from decimal import Decimal
import unittest

from lib.design import Element
from lib.design.dch_compat import restore_legacy_dimensions


def symbol():
    part=Element('Part')
    part.add('Width',9)
    part.add('Height',9)
    part.add('Pins')
    part.add('Shapes')
    return part


class LegacyDimensionTests(unittest.TestCase):
    def test_empty_definition_has_no_artificial_selection_size(self):
        schematic=Element('Schematic')
        placed=schematic.add('Components').append(symbol())
        cached=schematic.add('CacheLib').add('Slots').add('Slot').add('Definition').append(symbol())
        # Footprints are unrelated to this focused bounds example.
        for owner in (placed,cached.parent):
            pattern=owner.add('Pattern')
            pattern.add('Width',0)
            pattern.add('Height',0)
        restore_legacy_dimensions(39,schematic)
        self.assertEqual((placed.scalar('Width'),placed.scalar('Height')),(Decimal('.36'),Decimal('.36')))
        self.assertEqual((cached.scalar('Width'),cached.scalar('Height')),(0,0))
        self.assertIsNone(cached.child('StoredData'))

    def test_modern_dimensions_are_literal_editable_data(self):
        schematic=Element('Schematic')
        placed=schematic.add('Components').append(symbol())
        restore_legacy_dimensions(40,schematic)
        self.assertEqual((placed.scalar('Width'),placed.scalar('Height')),(9,9))
        self.assertIsNone(placed.child('StoredData'))


if __name__=='__main__':
    unittest.main()
