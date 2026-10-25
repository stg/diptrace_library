"""Rigid transforms preserve geometry without quantizing arbitrary rotations."""
import math
import unittest

from lib.common.geometry import transform_point


class TransformTests(unittest.TestCase):
    def test_exact_quarter_turns_and_translation(self):
        for turns, expected in ((0, (12, 23)), (1, (13, 18)), (2, (8, 17)), (3, (7, 22)), (5, (13, 18))):
            with self.subTest(turns=turns):
                self.assertEqual(transform_point((2, 3), origin=(10, 20), angle=turns*math.pi/2), expected)

    def test_arbitrary_rotation_has_an_inverse_and_does_not_change_its_input(self):
        point = [2, -3]
        rotated = transform_point(point, angle=.37)
        restored = transform_point(rotated, angle=-.37)
        self.assertEqual(point, [2, -3])
        self.assertNotEqual(rotated, transform_point(point, angle=0))
        for actual, expected in zip(restored, point):
            self.assertAlmostEqual(actual, expected, places=13)

    def test_nonfinite_inputs_are_rejected(self):
        for arguments in (dict(point=(math.nan, 0)), dict(point=(0, 0), angle=math.inf),
                          dict(point=(0, 0), origin=(0, -math.inf))):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                transform_point(**arguments)


if __name__ == '__main__':
    unittest.main()
