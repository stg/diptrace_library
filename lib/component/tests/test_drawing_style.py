"""Inactive drawing text slots do not become independent library model facts."""
from pathlib import Path
import unittest

from lib.component.formats.eli.read import parse as parse_binary
from lib.component.formats.asc.read import parse as parse_asc
from lib.component.formats.elixml.read import parse as parse_xml
from lib.component.model import new_library, new_component, new_drawing

FIXTURES = Path(__file__).with_name('fixtures')


class SymbolDrawingStyleTests(unittest.TestCase):
    def test_nontext_inputs_keep_geometry_and_omit_inactive_text_style(self):
        for parser, name in ((parse_binary, 'connections_31.eli'), (parse_asc, 'connections.asc'),
                             (parse_xml, 'connections_input.elixml')):
            with self.subTest(input=name):
                document = parser((FIXTURES/name).read_bytes())
                shape = document.one('/Library/Components/Component/Parts/Part/Shapes/Shape')
                self.assertEqual(1, shape['Type'])
                self.assertEqual(2, len(shape.select('Points_New/pt')))
                self.assertAlmostEqual(.75, shape['PenWidth'])
                for name in ('FontSize', 'FontColor', 'FontType', 'TextAngle'):
                    self.assertIsNone(shape.get(name))
                self.assertEqual([], shape.select('TextLine/pt'))
                document.validate()

    def test_new_text_has_editable_style_and_nontext_can_retain_authored_words(self):
        document = new_library()
        component = document.one('/Library/Components').append(new_component('Example', 'U'))
        shapes = component.one('Parts/Part/Shapes')
        line = shapes.append(new_drawing(kind=1))
        line.one('TextLine').add('pt', 'Authored note')
        text = shapes.append(new_drawing(kind=10))
        text['FontSize'], text['FontName'], text['TextAngle'] = 9.25, 'Example font', 1.2
        text.one('TextLine').add('pt', 'Literal text')
        self.assertIsNone(line.get('FontSize'))
        clone = document.clone()
        self.assertEqual('Authored note', clone.one(line.path+'/TextLine/pt')['Text'])
        copied = clone.one(text.path)
        self.assertEqual((9.25, 'Example font', 1.2), tuple(copied[name] for name in ('FontSize', 'FontName', 'TextAngle')))
        document.validate()
        clone.validate()


if __name__ == '__main__':
    unittest.main()
