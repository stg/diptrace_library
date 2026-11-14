"""Meaningful drawing styles survive without retaining inactive wire slots."""
from pathlib import Path
import unittest

from lib.pattern.formats.lib.decode import decode
from lib.pattern.formats.lib.read import parse
from lib.pattern.formats.lib.write import encode
from lib.pattern.formats.libxml.read import parse as read_xml
from lib.pattern.model import new_drawing, new_library, new_pattern


FIXTURES = Path(__file__).with_name('fixtures')


class DrawingStyleTests(unittest.TestCase):
    def test_line_import_does_not_expose_inactive_font_settings(self):
        for document in (parse((FIXTURES/'geometry.lib').read_bytes()),
                         read_xml((FIXTURES/'geometry_input.libxml').read_bytes())):
            with self.subTest():
                shape = document.one('/Library/Patterns/Pattern/Shapes/Shape')
                self.assertEqual(1, shape['Type'])
                self.assertIsNone(shape.get('FontName'))
                self.assertIsNone(shape.get('FontSize'))
                self.assertIsNone(shape.get('TextAlign'))
                self.assertGreater(shape['Width'], 0)
                self.assertFalse(document.one('/Library/Patterns/Pattern')['Sided'])
                document.validate()

    def test_writer_generates_unused_slots_without_changing_live_drawing(self):
        document = parse((FIXTURES/'geometry.lib').read_bytes())
        shape = document.one('/Library/Patterns/Pattern/Shapes/Shape')
        output = encode(document)
        serialized = decode(output).root.one('Patterns/Pattern/Shapes/Shape[2]')
        self.assertEqual(('', 6, -1, 0), tuple(serialized[name] for name in
                         ('FontName', 'FontSize', 'FontWidth', 'TextAlign')))
        for current in (shape, parse(output).one('/Library/Patterns/Pattern/Shapes/Shape')):
            self.assertIsNone(current.get('FontSize'))
            self.assertGreater(current['Width'], 0)

    def test_new_text_style_and_nonempty_content_survive(self):
        document = new_library()
        pattern = new_pattern('Example')
        document.one('/Library/Patterns').append(pattern)
        line = new_drawing(kind=1)
        self.assertIsNone(line.get('FontSize'))
        line.one('Points_New').add('pt', 0, 0)
        line.one('Points_New').add('pt', 1, 1)
        # A nonempty string is authored content, even on a non-text drawing.
        line.one('TextLine').add('pt', 'Retain authored words')
        pattern.one('Shapes').append(line)
        text = new_drawing(kind=7)
        text['FontName'], text['FontSize'] = 'Example font', 7.25
        text.one('TextLine').add('pt', 'Visible text')
        pattern.one('Shapes').append(text)
        result = parse(encode(document)).one('/Library/Patterns/Pattern')
        self.assertEqual('Retain authored words', result.one('Shapes/Shape[1]/TextLine/pt')['Text'])
        self.assertEqual(('Example font', 7.25), tuple(result.one('Shapes/Shape[2]')[name]
                         for name in ('FontName', 'FontSize')))

    def test_xml_text_extents_are_numeric_calculations_not_authored_fields(self):
        source = (FIXTURES/'metadata_input.libxml').read_text(encoding='utf-8')
        source = source.replace('Type="Text"', 'Type="Text" TextWidth="12.345" TextHeight="4.567"')
        document = read_xml(source)
        shape = document.one('/Library/Patterns/Pattern/Shapes/Shape')
        self.assertEqual(7.25, shape['FontSize'])
        self.assertNotIn('TextWidth', shape.schema.fields)
        self.assertNotIn('TextHeight', shape.schema.fields)
        document.validate()


if __name__ == '__main__':
    unittest.main()
