"""A curve on the old conversion boundary remains a curve in modern output."""
from decimal import Decimal
import unittest

import lib
from lib.common.asc import dumps
from lib.common.model import Element
from lib.common.symbol_geometry import expand_legacy_drawing
from lib.schematic.formats.capabilities import DCH
from lib.schematic.model.objects import new_symbol, new_symbol_shape


class LegacyCurveStabilityTests(unittest.TestCase):
    def test_modern_dch_does_not_reapply_old_curve_classification(self):
        document = lib.new_schematic()
        part = document.one('/Schematic/Components').append(new_symbol('Curve', 'U1'))
        part['Width'], part['Height'] = 18, 12
        for index, kind in enumerate((6, 7)):
            legacy = Element('Shape')
            legacy.add('Type', kind)
            points = legacy.add('Points')
            points.add('pt', 0, 0)
            points.add('pt', 1, Decimal('1.3'))
            expand_legacy_drawing(legacy)
            shape = part.one('Shapes').append(new_symbol_shape(index))
            shape['Type'] = legacy['Type']
            for point in legacy.select('Points_New/pt'):
                shape.one('Points_New').add('pt', *point.values)
        document.validate()
        before = dumps(document, preserve=False)
        for version in DCH.write_versions:
            with self.subTest(version=version):
                data = lib.serialize(document, format='dch', version=version, report=lib.ConversionReport())
                loaded = lib.parse(data, report=lib.ConversionReport())
                curves = [shape for shape in loaded.select('/Schematic/Components/Part/Shapes/Shape')
                          if shape['Type'] in (6, 7, 8, 9)]
                self.assertEqual([shape['Type'] for shape in curves], [6, 7])
                self.assertEqual([len(shape.select('Points_New/pt')) for shape in curves], [2, 2])
                self.assertEqual(lib.serialize(loaded, format='dch', version=version,
                                               report=lib.ConversionReport()), data)
                self.assertEqual(dumps(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
