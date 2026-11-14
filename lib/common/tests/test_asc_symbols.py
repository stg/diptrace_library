"""Current multiline symbol text takes precedence over its legacy first line."""
import unittest

from lib.common.asc_symbols import unpack_symbol_shape
from lib.common.model import Element


class SymbolAsciiTests(unittest.TestCase):
    def test_current_lines_and_points_replace_legacy_views(self):
        shape = Element('Shape', 0)
        shape.add('Name', 'Old first line')
        shape.add('Points').add('pt', 100, 200)
        current = shape.add('Points_New')
        current.add('pt', 1, 2)
        lines = shape.add('TextLines')
        first = lines.add('pt', 'Current first line')
        lines.add('pt', '')
        lines.add('pt', 'Current last line')
        unpack_symbol_shape(shape)
        self.assertIs(current, shape.one('Points_New'))
        self.assertIs(first, shape.one('TextLine').children()[0])
        self.assertEqual(['Current first line', '', 'Current last line'],
                         [row.values[0] for row in shape.one('TextLine').children()])
        self.assertIsNone(shape.child('Points'))
        self.assertIsNone(shape.child('TextLines'))

    def test_legacy_first_line_is_used_only_without_current_lines(self):
        shape = Element('Shape', 0)
        shape.add('Name', 'Legacy text')
        unpack_symbol_shape(shape)
        self.assertEqual(('Legacy text',), shape.one('TextLine/pt').values)
        self.assertEqual([], shape.one('Points_New').children())
        unpack_symbol_shape(shape)
        self.assertEqual(1, len(shape.select('TextLine/pt')))

    def test_invalid_or_duplicate_current_lines_are_rejected(self):
        for invalid in ('duplicate', 'count', 'type', 'row'):
            with self.subTest(invalid=invalid):
                shape = Element('Shape', 0)
                lines = shape.add('TextLines', *((1,) if invalid == 'count' else ()))
                lines.add('BadRow' if invalid == 'row' else 'pt', 123 if invalid == 'type' else 'Text')
                if invalid == 'duplicate':
                    shape.add('TextLine')
                with self.assertRaises(ValueError):
                    unpack_symbol_shape(shape)


if __name__ == '__main__':
    unittest.main()
