"""Complete standalone input produces current editable component identities."""
from pathlib import Path
import unittest

from lib.common.conversion import ConversionReport
from lib.component.formats.eli.read import parse

FIXTURES = Path(__file__).with_name('fixtures')


class BinaryReadTests(unittest.TestCase):
    def test_named_component_and_physical_pin_links_are_editable(self):
        document = parse((FIXTURES/'parameters.eli').read_bytes())
        component = document.one('/Library/Components/Component')
        pattern = component.one('Pattern')
        pins = component.select('Parts/Part/Pins/Pin')
        pads = pattern.select('Pads/Pad')
        self.assertEqual('Example component', component['Name'])
        self.assertEqual(2, len(pads))
        self.assertIs(pads[0], pins[0]['Pad'])
        self.assertIs(pads[1], pins[1]['Pad'])
        self.assertEqual((3.25, True), (pins[0]['NameFontSize'], pins[0]['NameFontMono']))
        pads[1].move_to(pattern.one('Pads'), index=0)
        self.assertEqual((2, 1), tuple(pin['Number'] for pin in pins))
        self.assertIs(pads[1], pattern.one('Shapes/Shape')['Pad'])
        document.validate()

    def test_multipart_shared_metadata_has_one_owner_in_each_output_revision(self):
        for version in (31, 32, 33):
            with self.subTest(version=version):
                report = ConversionReport()
                document = parse((FIXTURES/f'multipart_{version}.eli').read_bytes(), report=report)
                component = document.one('/Library/Components/Component')
                parts = component.select('Parts/Part')
                self.assertEqual(2, len(parts))
                self.assertEqual(['Gate A', 'Gate B'], [part['PartName'] for part in parts])
                self.assertEqual(['First value', 'Second value'], [part['Value'] for part in parts])
                self.assertEqual(['ExampleA', 'ExampleB'], [part['ModelString'] for part in parts])
                for part in parts:
                    self.assertEqual(('Example component', 'U', 'Example maker', 'https://example.invalid/device'),
                        tuple(part[name] for name in ('Name', 'RefDes', 'Manufacturer', 'Datasheet')))
                    self.assertIsNone(part.child('Name'))
                self.assertEqual(1, len(component.children('Pattern')))
                self.assertEqual('First note', component.one('UserFields/UserField')['Value'])
                parts[1]['Name'] = 'Renamed'
                self.assertEqual('Renamed', component['Name'])
                self.assertEqual(['Renamed', 'Renamed'], [part['Name'] for part in parts])
                self.assertEqual([], report.errors)
                document.validate()

    def test_cloning_and_parsing_do_not_retain_a_source_replay(self):
        data = (FIXTURES/'parameters.eli').read_bytes()
        before = bytes(data)
        document = parse(data)
        clone = document.clone()
        clone.one('/Library/Components/Component')['Name'] = 'Clone'
        self.assertEqual('Example component', document.one('/Library/Components/Component')['Name'])
        self.assertEqual(before, data)
        self.assertEqual([], document.unresolved())
        self.assertIsNone(document.root.source)
        clone.validate()


if __name__ == '__main__':
    unittest.main()
