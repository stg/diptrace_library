"""Definition construction preserves geometry unless placement requires a turn."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lib.design.cache import symbol_definition
from lib.design.schematic_objects import new_symbol, new_symbol_shape


class SymbolDefinitionTests(unittest.TestCase):
    def component(self, angle):
        part = new_symbol('Block', 'U1')
        part.set_field('Angle', angle)
        shape = part.one('Shapes').append(new_symbol_shape())
        shape.set_field('Type', 4)
        shape.one('Points_New').add('pt', 3, -1)
        shape.one('Points_New').add('pt', -2, 4)
        return part

    def test_unrotated_definition_keeps_corner_order(self):
        for angle in (0, 360, -720):
            with self.subTest(angle=angle):
                source = self.component(angle)
                definition = symbol_definition(source)
                self.assertEqual([p.values for p in definition.select('Shapes/Shape/Points_New/pt')],
                                 [(3, -1), (-2, 4)])

    def test_quarter_turn_normalizes_corners_on_the_owned_definition(self):
        for angle, expected in ((90, [(-4, -2), (1, 3)]),
                                (450, [(-4, -2), (1, 3)]),
                                (-90, [(-1, -3), (4, 2)])):
            with self.subTest(angle=angle):
                source = self.component(angle)
                definition = symbol_definition(source)
                self.assertEqual([p.values for p in definition.select('Shapes/Shape/Points_New/pt')], expected)
                self.assertEqual([p.values for p in source.select('Shapes/Shape/Points_New/pt')],
                                 [(3, -1), (-2, 4)])


if __name__ == '__main__':
    unittest.main()
