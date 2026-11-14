"""Library symbol frames use the body envelope, including template types."""
import unittest

from lib.common.unplaced_symbol_frame import normalize_frame
from lib.component.model import new_component, new_pin, new_drawing, new_group


class SymbolFrameTests(unittest.TestCase):
    def test_asymmetric_free_and_template_bodies_share_one_frame_rule(self):
        for kind in (0, 1):
            with self.subTest(kind=kind):
                part = new_component().one('Parts/Part')
                for name, value in dict(Type=kind, Width=24, Height=18, Origin_X=.45, Origin_Y=-.75).items():
                    part[name] = value
                for x, y in ((3, 6), (15, -12)):
                    pin = part.one('Pins').append(new_pin())
                    pin['X'], pin['Y'] = x, y
                    pin['Length'] = 300  # Pin graphics do not enlarge this envelope.
                shape = part.one('Shapes').append(new_drawing())
                shape['PenWidth'] = 90
                for point in ((0, 0), (3, 0)):
                    shape.one('Points_New').add('pt', *point)
                text = part.one('Shapes').append(new_drawing(kind=10))
                text.one('Points_New').add('pt', 300, 400)
                group = part.one('Groups').append(new_group())
                normalize_frame(part)
                self.assertEqual((15, 18), (part['Width'], part['Height']))
                self.assertEqual((-7.05, 2.25), (part['Origin_X'], part['Origin_Y']))
                self.assertEqual([(-4.5, 9), (7.5, -9)],
                    [(pin['X'], pin['Y']) for pin in part.select('Pins/Pin')])
                self.assertEqual([(-7.5, 3), (-4.5, 3)],
                    [point.values for point in shape.select('Points_New/pt')])
                self.assertEqual((292.5, 403), text.one('Points_New/pt').values)
                # An empty group has no independent position to translate.
                self.assertEqual((0, 0), (group['X'], group['Y']))
                snapshot = [(node.path, node.values) for node in part.walk(include_self=True)]
                normalize_frame(part)
                self.assertEqual(snapshot, [(node.path, node.values) for node in part.walk(include_self=True)])

    def test_an_empty_symbol_keeps_its_independent_origin(self):
        part = new_component().one('Parts/Part')
        part['Origin_X'], part['Origin_Y'] = 7, 9
        normalize_frame(part)
        self.assertEqual((0, 0, 7, 9),
                         tuple(part[name] for name in ('Width', 'Height', 'Origin_X', 'Origin_Y')))


if __name__ == '__main__':
    unittest.main()
