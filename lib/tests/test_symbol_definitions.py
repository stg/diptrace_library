"""Definition construction preserves geometry unless placement requires a turn."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.schematic.model.cache import (symbol_definition)
from lib.schematic.model.objects import (new_symbol, new_symbol_shape)
from lib.common.model import SourceSpan
from lib.common.symbol_records import SYMBOL


class SymbolDefinitionTests(unittest.TestCase):
    def test_import_defaults_accept_a_synthesized_typed_definition(self):
        from lib import Element
        from lib.schematic.formats.dch.compat import complete_properties
        source = self.component(0)
        schematic = Element('Schematic')
        schematic.add('Components')
        cache = schematic.add('CacheLib')
        cache.add('Patterns')
        slot = cache.add('Slots').add('Slot', 0, '')
        definition = slot.add('Definition', 0)
        symbol = definition.append(symbol_definition(source))
        definition.append(source.one('Pattern').clone())
        symbol['ModelNote'] = 'authored note'
        complete_properties(schematic)
        self.assertEqual(symbol['ModelNote'], 'authored note')
        incomplete = Element('Part', *symbol.arguments)
        for child in symbol.children():
            if child.kind != 'ModelNote':
                incomplete.append(child.clone())
        symbol.detach()
        definition.append(incomplete.bind_schema(SYMBOL))
        complete_properties(schematic)
        self.assertEqual(incomplete['ModelNote'], '')

    def test_current_definition_is_independent_and_retains_selected_field_details(self):
        source = self.component(0)
        width = source.one('Width')
        width.source = SourceSpan('test', 2, 5)
        width.annotations['note'] = ['original']
        definition = symbol_definition(source)
        self.assertIs(definition.schema, SYMBOL)
        copied = definition.one('Width')
        self.assertEqual(copied.source, width.source)
        self.assertEqual(copied.annotations, width.annotations)
        copied.annotations['note'].append('copy')
        definition['Width'] = 7
        self.assertNotEqual(definition['Width'], source['Width'])
        self.assertEqual(width.annotations, {'note': ['original']})
        self.assertIsNot(copied, width)

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
