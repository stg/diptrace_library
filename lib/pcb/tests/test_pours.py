"""Copper-pour fill data is separate from authored boundaries and settings."""
from decimal import Decimal, localcontext
import unittest

from lib.common.binary import BinaryWriter
from lib.common.model import Element
from lib.pcb.formats.dip.pours import read_base_pours
from lib.pcb.formats.dip.read import Reader


def pour_fixture(version):
    writer = BinaryWriter()
    writer.buffer.extend(b'\x07DTBOARD')
    writer.integer(version)

    def values(kind, *items):
        for item in items:
            getattr(writer, kind)(item)

    values('integer', 1)
    values('boolean', True, False, True)
    values('number', .3, .6, Decimal('1.2345'))
    values('integer', -1, 1, 2, 3)
    values('number', 0, 0, 3, 0, 0, 3)
    values('integer', 1)
    values('number', .3, .3, 2, .3)
    if version > 33:
        values('integer', 4)
    values('integer', 1, 3)
    values('number', 1, 1, 2, 1, 1, 2)
    if version > 33:
        values('integer', 5)
    values('integer', 0, 3)
    values('number', .6, .2)
    values('integer', 1)
    values('number', .5, .5, 1, .5, .2)
    if version > 33:
        values('integer', 6)
    values('boolean', True, True, False, False)
    values('number', .9)
    values('boolean', True, False, True)
    values('integer', 19)
    values('boolean', True, True)
    values('integer', 2)
    values('number', .25)
    values('boolean', False)
    if version > 33:
        values('boolean', True)
        values('integer', 7)
    values('integer', 17)
    return bytes(writer.buffer)


class PourTests(unittest.TestCase):
    def test_fill_geometry_and_region_gates_preserve_following_section(self):
        for version in (31, 33, 34, 37, 38, 54, 62):
            with self.subTest(version=version):
                reader = Reader(pour_fixture(version))
                upgrade = read_base_pours(reader, Element('Board'))[0]
                self.assertEqual(reader.integer(), 17)
                self.assertEqual(reader.pos, len(reader.data))
                pour = upgrade.pour
                self.assertTrue(pour['Poured'])
                self.assertEqual(pour['NetId'], 2)
                self.assertEqual(pour['Priority'], 7 if version > 33 else 0)
                self.assertEqual(upgrade.regions_counted, version >= 38)
                self.assertEqual(upgrade.previous_number, 19)
                self.assertEqual(len(pour.one('Points').children()), 3)
                self.assertEqual(pour.one('Fill/Lines/Line')['Region'], 4 if version > 33 else -1)
                self.assertEqual(pour.one('Fill/SpokeLine/Line')['Width'], Decimal('.2'))
                self.assertEqual(pour.one('Fill/Polygons/Poly')['Region'], 5 if version > 33 else -1)
                self.assertIsNone(pour.child('Regions_Counted'))

    def test_area_is_an_area_and_is_independent_of_caller_decimal_precision(self):
        data = pour_fixture(54)
        with localcontext() as context:
            context.prec = 2
            pour = read_base_pours(Reader(data), Element('Board'))[0].pour
        self.assertEqual(pour['MinimumArea'], Decimal('1.52399025'))


if __name__ == '__main__':
    unittest.main()
