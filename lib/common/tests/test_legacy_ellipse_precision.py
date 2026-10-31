"""An old curve's representation must not depend on its translated origin."""
from decimal import Decimal, localcontext
import unittest

from lib.common.model import Element
from lib.common.symbol_geometry import expand_legacy_drawing
from lib.common.footprint_geometry import expand_normalized_drawing


ORIGINS = (('0', '0'), ('-.2', '-.1'), ('37.1', '-5.3'))
BOUNDARIES = ('.2999', '.3', '.3001')


class LegacyEllipsePrecisionTests(unittest.TestCase):
    def test_symbol_cutoff_is_exact_and_translation_independent(self):
        for origin in ORIGINS:
            x, y = map(Decimal, origin)
            for difference in BOUNDARIES:
                corners = ((x, y), (x+1, y+1+Decimal(difference)))
                polygon = Decimal(difference) > Decimal('.3')
                for kind in (6, 7):
                    for precision in (2, 28):
                        with self.subTest(origin=origin, difference=difference,
                                          kind=kind, precision=precision):
                            shape = Element('Shape')
                            shape.add('Type', kind)
                            points = shape.add('Points')
                            for point in corners:
                                points.add('pt', *point)
                            with localcontext() as context:
                                context.prec = precision
                                expand_legacy_drawing(shape)
                            self.assertEqual(shape['Type'], kind+2 if polygon else kind)
                            result = shape.select('Points_New/pt')
                            self.assertEqual(len(result), (31 if kind == 6 else 30) if polygon else 2)
                            if not polygon:
                                self.assertEqual(tuple(point.values for point in result), corners)

    def test_footprint_cutoff_uses_controls_before_floating_scale(self):
        for origin in ORIGINS:
            x, y = map(Decimal, origin)
            controls = ((x, y), (x+1, y+1))
            for difference in BOUNDARIES:
                size = (Decimal(1), Decimal(1)+Decimal(difference))
                polygon = Decimal(difference) > Decimal('.3')
                for kind, target in ((3, 8), (5, 9)):
                    for precision in (2, 28):
                        with self.subTest(origin=origin, difference=difference,
                                          kind=kind, precision=precision):
                            with localcontext() as context:
                                context.prec = precision
                                result_kind, points = expand_normalized_drawing(kind, controls, (), size)
                            self.assertEqual(result_kind, target if polygon else kind)
                            self.assertEqual(len(points), (31 if kind == 3 else 30) if polygon else 2)
                            if not polygon:
                                self.assertEqual(points, tuple((float(a), float(b)*float(size[1]))
                                                             for a, b in controls))


if __name__ == '__main__':
    unittest.main()
