"""Optional library URLs have one meaning across empty slots and omitted XML."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from lib.pattern.formats.lib.read import parse as parse_binary
from lib.pattern.formats.asc.read import parse as parse_asc
from lib.pattern.formats.libxml.read import parse as parse_xml

FIXTURES = Path(__file__).with_name('fixtures')


class OptionalFieldTests(unittest.TestCase):
    def test_empty_datasheet_normalizes_to_absent_in_every_input(self):
        for parser, filename in ((parse_binary, 'geometry.lib'), (parse_asc, 'geometry.asc'),
                                 (parse_xml, 'geometry_input.libxml')):
            with self.subTest(format=filename):
                document = parser((FIXTURES/filename).read_bytes())
                pattern = document.one('/Library/Patterns/Pattern')
                self.assertIsNone(pattern.get('Datasheet'))
                self.assertIsNone(pattern.child('Datasheet'))
                document.validate()

    def test_explicit_nonempty_datasheet_is_retained(self):
        root = ET.fromstring((FIXTURES/'geometry_input.libxml').read_bytes())
        pattern = root.find('Patterns/Pattern')
        url = ET.SubElement(pattern, 'Datasheet')
        url.text = 'https://example.invalid/package'
        document = parse_xml(ET.tostring(root, encoding='utf-8'))
        self.assertEqual(url.text, document.one('/Library/Patterns/Pattern')['Datasheet'])


if __name__ == '__main__':
    unittest.main()
