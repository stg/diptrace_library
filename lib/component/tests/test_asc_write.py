"""ASC output preserves current data apart from its explicit format limits."""
from pathlib import Path
import unittest

from lib.common.conversion import ConversionReport
from lib.common.errors import UnsupportedFileError
from lib.component.formats.asc.read import parse
from lib.component.formats.asc.write import dumps
from lib.component.formats.eli.read import parse as parse_binary
from lib.component.model import new_library, new_component, new_part, new_group, new_drawing
from .test_asc_read import facts

FIXTURES = Path(__file__).with_name('fixtures')


class AsciiWriteTests(unittest.TestCase):
    def test_receiver_layout_defaults_are_optional_and_do_not_move_authored_text(self):
        from lib.common.text.layout import TextLayout
        from lib.component.formats.asc.write import project_document
        document = new_library()
        part = document.one('/Library/Components').append(new_component('Text','U')).one('Parts/Part')
        shape = part.one('Shapes').append(new_drawing(kind=10))
        shape.one('Points_New').add('pt', 0, 0)
        for key, value in dict(FontSize=6, FontWidth=-1, TextAngle=0,
                TextHorz=-1, TextVert=-1, LineSpacing=1.2).items():
            shape[key] = value
        for line in ('Control','Second line'):
            shape.one('TextLine').add('pt', line)
        before = facts(document)
        def height(**kwargs):
            syntax = project_document(document, **kwargs)
            points = syntax.one('/Library/Components/Component/Part/Shapes/Shape/Points').children('pt')
            return points[1].values[1]-points[0].values[1]
        classic = height(target_application='4.3.0.5')
        current = height(target_application='5.3.5.1')
        self.assertGreater(current, classic)
        self.assertEqual(classic, height(target_application='5.3.5.1', text_layout=TextLayout()))
        self.assertEqual(before, facts(document))

    def assertFacts(self, before, after):
        self.assertEqual(before.keys(), after.keys())
        for key, value in before.items():
            if isinstance(value, float):
                self.assertAlmostEqual(value, after[key], delta=.0001, msg=key)
            else:
                self.assertEqual(value, after[key], key)

    def test_native_ascii_inputs_preserve_every_named_field_and_link(self):
        for name in ('connections.asc', 'multipart_33.asc', 'text_33.asc'):
            with self.subTest(input=name):
                document = parse((FIXTURES/name).read_bytes())
                before = facts(document)
                result = parse(dumps(document, report=ConversionReport()))
                self.assertFacts(before, facts(result))
                self.assertEqual(before, facts(document))
                result.validate()

    def test_declared_losses_are_reported_without_mutating_source(self):
        document = parse_binary((FIXTURES/'parameters.eli').read_bytes())
        before = facts(document)
        report = ConversionReport()
        result = parse(dumps(document, report=report))
        expected = dict(before)
        for key in expected:
            if key.endswith(('/NameFontMono', '/FontMono')):
                expected[key] = False
            elif '/Pattern[' in key and '/Shapes[' in key:
                if key.endswith('/Pad'):
                    expected[key] = None
                elif key.endswith('/PadId'):
                    expected[key] = -1
        self.assertFacts(expected, facts(result))
        self.assertEqual(before, facts(document))
        self.assertEqual({'monospaced-font', 'drawing-pad-reference'}, {notice.rule for notice in report.warnings})

    def test_groups_reordered_pads_and_connections_are_generated_from_identity(self):
        document = parse((FIXTURES/'connections.asc').read_bytes())
        component = document.one('/Library/Components/Component')
        part = component.select('Parts/Part')[0]
        group = part.one('Groups').append(new_group())
        pin = part.select('Pins/Pin')[0]
        pin['Group'] = group
        pattern = component.one('Pattern')
        pads = pattern.select('Pads/Pad')
        pads[1].move_to(pattern.one('Pads'), index=0)
        before = facts(document)
        result = parse(dumps(document, report=ConversionReport()))
        self.assertFacts(before, facts(result))

    def test_empty_and_unattached_multiple_parts(self):
        document = new_library('Empty')
        self.assertEqual([], parse(dumps(document)).select('/Library/Components/Component'))
        component = document.one('/Library/Components').append(new_component('Example', 'U'))
        component.one('Parts').append(new_part('Gate B'))
        result = parse(dumps(document))
        self.assertEqual(2, len(result.select('/Library/Components/Component/Parts/Part')))
        self.assertEqual([], result.select('/Library/Components/Component/Pattern'))

    def test_text_projection_and_stability(self):
        document = parse((FIXTURES/'text_33.asc').read_bytes())
        component = document.one('/Library/Components/Component')
        component['Name'] = 'A "quoted" Ω'
        report = ConversionReport()
        text = dumps(document, report=report)
        self.assertIn('A !quoted! O', text)
        self.assertEqual({'asc-text-sanitization', 'asc-text-encoding'}, {notice.rule for notice in report.warnings})
        first = facts(parse(text))
        for _ in range(5):
            text = dumps(parse(text))
        self.assertEqual(first, facts(parse(text)))
        self.assertEqual('A "quoted" Ω', component['Name'])

    def test_revision_gate(self):
        report = ConversionReport()
        with self.assertRaises(UnsupportedFileError):
            dumps(new_library(), version=32, report=report)
        self.assertEqual(1, len(report.errors))

    def test_old_receiver_rounds_sizes_without_changing_the_model(self):
        document = parse_binary((FIXTURES/'parameters.eli').read_bytes())
        before = facts(document)
        for application in ('4.3.0.5', '4.9.5.0'):
            with self.subTest(application=application):
                report = ConversionReport()
                result = parse(dumps(document, target_application=application, report=report))
                pin = result.select('/Library/Components/Component/Parts/Part/Pins/Pin')[0]
                self.assertEqual(3, pin['NameFontSize'])
                self.assertEqual(7, result.one('/Library/Components/Component/Pattern/Shapes/Shape')['FontSize'])
                self.assertIn('fractional-font-size', {notice.rule for notice in report.warnings})
                self.assertEqual(before, facts(document))


if __name__ == '__main__':
    unittest.main()
