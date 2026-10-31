"""Shared footprint expansion preserves the defining geometry of each kind."""
import unittest

from lib.common.footprint_geometry import expand_normalized_drawing


class FootprintGeometryTests(unittest.TestCase):
    controls = ((.1, .2), (.9, .8), (.5, .1))

    def test_primitives_text_and_polygons_select_their_own_controls(self):
        for kind, count in ((0, 0), (1, 2), (2, 2), (4, 2), (6, 3)):
            with self.subTest(kind=kind):
                actual_kind, points = expand_normalized_drawing(kind, self.controls, (), (10, 20))
                self.assertEqual(actual_kind, kind)
                self.assertEqual(points, tuple((x*10, y*20) for x, y in self.controls[:count]))
        for orientation, expected in enumerate(((1., 4.), (1., 16.), (9., 16.), (9., 4.))):
            self.assertEqual(expand_normalized_drawing(7, self.controls, (), (10, 20),
                text_orientation=orientation), (7, (expected,)))
        self.assertEqual(expand_normalized_drawing(9, self.controls, ((.3, .5),), (10, 20)),
                         (9, ((3., 10.),)))

    def test_ellipse_sampling_retains_extents_and_closure(self):
        for source, target, count in ((3, 8, 31), (5, 9, 30)):
            with self.subTest(kind=source):
                kind, points = expand_normalized_drawing(source, ((0, 0), (1, 1)), (), (10, 4))
                self.assertEqual((kind, len(points)), (target, count))
                self.assertEqual(points[0], (10., 2.))
                self.assertAlmostEqual(min(p[0] for p in points), 0)
                if source == 3:
                    self.assertEqual(points[0], points[-1])
        self.assertEqual(expand_normalized_drawing(3, ((0, 0), (1, 1)), (), (4, 4)),
                         (3, ((0., 0.), (4., 4.))))

    def test_mirrored_text_selects_opposite_horizontal_corner_at_each_quarter_turn(self):
        for orientation, expected in enumerate(((9., 4.), (9., 16.), (1., 16.), (1., 4.))):
            with self.subTest(orientation=orientation):
                self.assertEqual(expand_normalized_drawing(7, self.controls, (), (10, 20),
                    text_orientation=orientation, text_mirrored=True), (7, (expected,)))
        # Mirroring selects a text anchor; it does not reflect other drawings.
        self.assertEqual(expand_normalized_drawing(2, self.controls, (), (10, 20),
            text_mirrored=True), (2, ((1., 4.), (9., 16.))))


if __name__ == '__main__':
    unittest.main()
