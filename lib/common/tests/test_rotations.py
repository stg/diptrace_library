"""Equivalent angular reflections share their exact computed rotation factors."""
from decimal import Decimal, localcontext
import math
import unittest

from lib.common.geometry import reflected_angle, rotation_components, transform_point


class RotationTests(unittest.TestCase):
    def test_reflection_changes_only_the_sine_sign(self):
        for angle in map(Decimal, ('.3', '1.570785307179586', '4.7124', '-5.4', '123.456')):
            with self.subTest(angle=angle):
                cosine, sine = rotation_components(angle)
                self.assertEqual(rotation_components(reflected_angle(angle)), (cosine, -sine))
                x, y = transform_point((1, 0), angle=angle)
                self.assertEqual(transform_point((1, 0), angle=reflected_angle(angle)), (x, -y))

    def test_cardinal_reflections_keep_integer_matrices(self):
        for angle, expected in ((0, (1, 0)), (math.pi/2, (0, 1)),
                                 (math.pi, (-1, 0)), (3*math.pi/2, (0, -1))):
            for sign in (-1, 1):
                with self.subTest(angle=angle, sign=sign):
                    value = Decimal(str(angle))*sign
                    cosine, sine = expected[0], sign*expected[1]
                    self.assertEqual(rotation_components(value), (cosine, sine))
                    self.assertEqual(rotation_components(reflected_angle(value)), (cosine, -sine))

    def test_period_reduction_ignores_ambient_precision_and_keeps_near_cardinals(self):
        angle = Decimal('1.57079632679489660001')
        expected = rotation_components(angle)
        self.assertNotEqual(expected[0], 0)
        turn = Decimal(str(math.tau))
        shifted = angle + 1000*turn
        with localcontext() as context:
            context.prec = 3
            self.assertEqual(rotation_components(shifted), expected)
            self.assertEqual(rotation_components(reflected_angle(angle)), (expected[0], -expected[1]))


if __name__ == '__main__':
    unittest.main()
