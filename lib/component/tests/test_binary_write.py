"""Standalone ELI output preserves current data and projects declared revisions."""
from pathlib import Path
import unittest

from lib.common.conversion import ConversionReport
from lib.common.errors import UnsupportedFileError
from lib.component.formats.eli.decode import decode
from lib.component.formats.eli.read import parse
from lib.component.formats.eli.write import encode
from lib.component.model import new_library, new_component, new_part
from .test_asc_read import facts

FIXTURES = Path(__file__).with_name('fixtures')


class BinaryWriteTests(unittest.TestCase):
    def test_current_revision_preserves_all_named_facts_and_links(self):
        for name in ('parameters.eli', 'multipart_33.eli', 'text_33.eli', 'secondary_connections_33.eli'):
            with self.subTest(input=name):
                document = parse((FIXTURES/name).read_bytes())
                before = facts(document)
                report = ConversionReport()
                output = encode(document, report=report)
                after = facts(parse(output))
                self.assertEqual(before.keys(), after.keys())
                for key, value in before.items():
                    if isinstance(value, float):
                        self.assertAlmostEqual(value, after[key], delta=.0001, msg=key)
                    else:
                        self.assertEqual(value, after[key], key)
                self.assertEqual(before, facts(document))
                self.assertEqual([], report.notices)

    def test_older_revision_font_and_drawing_link_losses_are_detached_and_reported(self):
        document = parse((FIXTURES/'parameters.eli').read_bytes())
        before = facts(document)
        for version in (31, 32):
            with self.subTest(version=version):
                report = ConversionReport()
                data = encode(document, version=version, report=report)
                self.assertEqual(version, decode(data).header.version)
                result = parse(data)
                component = result.one('/Library/Components/Component')
                pin = component.select('Parts/Part/Pins/Pin')[0]
                drawing = component.one('Pattern/Shapes/Shape')
                self.assertEqual((3, False), (pin['NameFontSize'], pin['NameFontMono']))
                self.assertEqual((7, False), (drawing['FontSize'], drawing['FontMono']))
                self.assertEqual(-1 if version==31 else 2, drawing['PadId'])
                rules = {notice.rule for notice in report.warnings}
                self.assertIn('fractional-font-size', rules)
                self.assertIn('monospaced-font', rules)
                self.assertEqual(version==31, 'drawing-pad-reference' in rules)
                self.assertEqual(before, facts(document))

    def test_empty_and_unattached_multipart_libraries(self):
        empty = new_library('Empty', hint='No entries')
        for version in (31, 32, 33):
            result = parse(encode(empty, version=version))
            self.assertEqual('Empty', result.one('/Library')['Name'])
            self.assertEqual([], result.select('/Library/Components/Component'))
        document = new_library()
        component = document.one('/Library/Components').append(new_component('Example', 'U'))
        component.one('Parts').append(new_part('Gate B'))
        result = parse(encode(document))
        self.assertEqual(2, len(result.select('/Library/Components/Component/Parts/Part')))
        self.assertEqual([], result.select('/Library/Components/Component/Pattern'))

    def test_reordered_pad_links_survive_output(self):
        document = parse((FIXTURES/'connections_33.eli').read_bytes())
        pattern = document.one('/Library/Components/Component/Pattern')
        pads = pattern.select('Pads/Pad')
        pads[1].move_to(pattern.one('Pads'), index=0)
        result = parse(encode(document))
        component = result.one('/Library/Components/Component')
        pair = component.one('Pattern/InternalConnections/IntCon')
        self.assertEqual((2, 1), pair.values)
        self.assertEqual(['2', '1'], [pad['StringNumber'] for pad in component.select('Pattern/Pads/Pad')])
        self.assertEqual((2, 1), tuple(pin['Number'] for pin in component.select('Parts/Part/Pins/Pin')))

    def test_repeat_conversion_is_stable_without_source_replay(self):
        document = parse((FIXTURES/'parameters.eli').read_bytes())
        first = facts(parse(encode(document)))
        for _ in range(10):
            document = parse(encode(document))
        self.assertEqual(first, facts(document))
        self.assertIsNone(document.root.source)

    def test_unimplemented_output_and_invalid_version_are_explicit_errors(self):
        document = parse((FIXTURES/'parameters.eli').read_bytes())
        report = ConversionReport()
        with self.assertRaises(UnsupportedFileError):
            encode(document, version=30, report=report)
        self.assertTrue(report.errors)
        pin = document.one('/Library/Components/Component').select('Parts/Part/Pins/Pin')[0]
        pin['Pad'] = None
        pin.add('UnresolvedPadId', 999)
        document.references.note(pin, 'component-pin-pad: unavailable key 999',
                                 collections=(document.one('/Library/Components/Component/Pattern/Pads'),))
        report = ConversionReport()
        result = parse(encode(document, report=report))
        self.assertEqual([], result.references.issues)
        self.assertIsNone(result.one('/Library/Components/Component').select('Parts/Part/Pins/Pin')[0]['Pad'])
        self.assertIn('unresolved-local-reference', {notice.rule for notice in report.warnings})
        self.assertEqual(999, pin['UnresolvedPadId'])


if __name__ == '__main__':
    unittest.main()
