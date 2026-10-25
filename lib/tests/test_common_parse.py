"""Each in-memory format imports into the same editing and conversion API."""
import unittest

from lib import ExportReport, new_schematic, parse, parse_source
from lib.schematic.model.objects import (new_symbol)
from lib.schematic.model.refs import (bind_schematic_references)


def encode(document, format):
    return getattr(document, 'to_'+format+'_bytes')(report=ExportReport())


class CommonParseTests(unittest.TestCase):
    def test_each_input_can_be_searched_edited_moved_and_written_in_each_format(self):
        original = new_schematic()
        first = original.one('/Schematic/Components').append(new_symbol('Resistor', 'R1'))
        first.set_field('Value', '4k7')
        original.one('/Schematic/Components').append(new_symbol('Capacitor', 'C1'))
        bind_schematic_references(original)
        for source_format in ('dch', 'asc', 'dchxml'):
            with self.subTest(source=source_format):
                current = parse(encode(original, source_format), format=source_format)
                part = current.one('/Schematic/Components/Part[Value="4k7"]')
                part.set_field('Value', 'edited')
                part.move_to(part.parent, 1)
                current.rebuild()
                for target_format in ('dch', 'asc', 'dchxml'):
                    with self.subTest(target=target_format):
                        reloaded = parse(encode(current, target_format), format=target_format)
                        parts = reloaded.select('/Schematic/Components/Part')
                        self.assertEqual([row.values[1] for row in parts], ['C1', 'R1'])
                        self.assertEqual(parts[1].scalar('Value'), 'edited')
                        self.assertEqual(reloaded.references.issues, [])

    def test_source_views_are_explicit_and_text_or_byte_input_use_the_same_model(self):
        source = new_schematic()
        data = encode(source, 'asc')
        raw = parse_source(data, format='.ASC')
        self.assertEqual(raw.one('/Units').values, ('mm',))
        for value in (data, data.decode('cp1252'), bytearray(data), memoryview(data)):
            current = parse(value, format='asc')
            self.assertEqual(current.select('/Units'), [])
            self.assertTrue(current.one('/Schematic/Settings').scalar('UnitsMM'))
        with self.assertRaisesRegex(ValueError, 'unsupported file format'):
            parse(data, format='unknown')


if __name__ == '__main__':
    unittest.main()
