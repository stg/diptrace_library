"""Standalone field-selected text remains authored library template content."""
from pathlib import Path
import unittest

from lib.component.formats.eli.read import parse as parse_binary
from lib.component.formats.asc.read import parse as parse_asc

FIXTURES = Path(__file__).with_name('fixtures')


class AuthoringTextTests(unittest.TestCase):
    def documents(self):
        for version in (31, 33):
            for parse, extension in ((parse_binary, 'eli'), (parse_asc, 'asc')):
                yield version, extension, parse((FIXTURES/f'text_{version}.{extension}').read_bytes())

    def test_template_text_is_not_replaced_with_placed_component_values(self):
        for version, extension, document in self.documents():
            with self.subTest(version=version, format=extension):
                component = document.one('/Library/Components/Component')
                for index, part in enumerate(component.select('Parts/Part')):
                    shapes = part.select('Shapes/Shape')
                    self.assertEqual([*range(7), 20], [shape['FontType'] for shape in shapes])
                    self.assertEqual([f'Authored-{index}-{position}' for position in range(8)],
                                     [shape.one('TextLine/pt')['Text'] for shape in shapes])
                document.validate()

    def test_authored_template_and_description_edits_remain_independent(self):
        for version, extension, document in self.documents():
            with self.subTest(version=version, format=extension):
                component = document.one('/Library/Components/Component')
                part = component.select('Parts/Part')[0]
                label = part.select('Shapes/Shape')[1]
                self.assertEqual(1, label['FontType'])
                label.one('TextLine/pt')['Text'] = 'Library template label'
                component['Name'] = 'Renamed component'
                part['Value'] = 'Changed value'
                self.assertEqual('Library template label', label.one('TextLine/pt')['Text'])
                clone = document.clone()
                self.assertEqual('Library template label', clone.one(label.path+'/TextLine/pt')['Text'])
                document.validate()
                clone.validate()


if __name__ == '__main__':
    unittest.main()
