"""Standalone ASC carries editable current data and reports its projections."""
import math
from pathlib import Path
import unittest

from lib.common.asc_library import loads_library
from lib.common.conversion import ConversionReport
from lib.common.errors import UnsupportedFileError
from lib.pattern.formats.lib.read import parse as read_binary
from lib.pattern.formats.asc.read import parse
from lib.pattern.formats.asc.write import dumps
from lib.pattern.model import new_library, new_pattern, new_drawing
from lib.pattern.tests.comparison import snapshot, assert_equivalent
from lib.pattern.tests.test_pad_defaults import fixture


FIXTURES = Path(__file__).with_name('fixtures')


class PatternAscWriteTests(unittest.TestCase):
    assert_equivalent = assert_equivalent

    def test_receiver_layout_defaults_reach_legacy_vector_text_corners(self):
        from lib.common.text.layout import TextLayout
        from lib.pattern.formats.asc.write import project_document
        document = new_library()
        pattern = document.one('/Library/Patterns').append(new_pattern('Text'))
        shape = pattern.one('Shapes').append(new_drawing(kind=7))
        shape.one('Points_New').add('pt', 0, 0)
        shape.one('TextLine').add('pt', 'Control')
        for key, value in dict(FontSize=6, FontWidth=-1, TextAngle=0,
                TextHorz=-1, TextVert=-1).items():
            shape[key] = value
        before = snapshot(document)
        def height(**kwargs):
            syntax = project_document(document, **kwargs)
            projected = syntax.one('/Library/Patterns/Pattern')
            header = projected.one('Shapes/Shape[2]').values
            return (header[6]-header[4])*projected['Height']
        classic = height(target_application='4.3.0.5')
        current = height(target_application='5.3.5.1')
        self.assertGreater(current, classic)
        self.assertEqual(classic, height(target_application='5.3.5.1', text_layout=TextLayout()))
        self.assertEqual(before, snapshot(document))

    def test_edited_reordered_data_and_dimension_links_survive(self):
        document = read_binary((FIXTURES/'geometry.lib').read_bytes())
        pattern = document.one('/Library/Patterns/Pattern')
        pattern.one('Pads/Pad[2]').move_to(pattern.one('Pads'), index=0)
        pattern.one('Pads/Pad[1]')['StringNumber'] = 'A17'
        before = snapshot(document)
        report = ConversionReport()
        output = parse(dumps(document, report=report))
        expected = document.clone()
        expected.one('/Library/Patterns/Pattern/Shapes/Shape')['Pad'] = None
        self.assert_equivalent(snapshot(expected), output)
        self.assertEqual(before, snapshot(document))
        self.assertEqual({'drawing-pad-reference'}, {n.rule for n in report.warnings})
        dimension = output.one('/Library/Patterns/Pattern/Dimensions/Dimension[1]')
        self.assertEqual((2, 1), (dimension['SubObject1'], dimension['SubObject2']))

    def test_fractional_font_and_multiline_text_with_explicit_mono_loss(self):
        document = read_binary((FIXTURES/'metadata.lib').read_bytes())
        report = ConversionReport()
        output = parse(dumps(document, report=report))
        shape = output.one('/Library/Patterns/Pattern/Shapes/Shape')
        self.assertEqual(7.25, shape['FontSize'])
        self.assertFalse(shape['FontMono'])
        self.assertEqual(['First line', 'Second line'], [r['Text'] for r in shape.select('TextLine/pt')])
        self.assertIsNone(shape['Pad'])
        self.assertEqual({'drawing-pad-reference', 'monospaced-font'}, {n.rule for n in report.warnings})
        expected = document.clone()
        expected_shape = expected.one('/Library/Patterns/Pattern/Shapes/Shape')
        expected_shape['Pad'], expected_shape['FontMono'] = None, False
        self.assert_equivalent(snapshot(expected), output)

    def test_old_receiver_has_integral_sizes_on_a_detached_view(self):
        document = read_binary((FIXTURES/'metadata.lib').read_bytes())
        before = snapshot(document)
        report = ConversionReport()
        result = parse(dumps(document, target_application='4.3.0.5', report=report))
        self.assertEqual(7, result.one('/Library/Patterns/Pattern/Shapes/Shape')['FontSize'])
        self.assertEqual(before, snapshot(document))
        self.assertIn('fractional-font-size', {notice.rule for notice in report.warnings})

    def test_rotated_standard_pad_projects_explicit_geometry_without_live_change(self):
        document, _, pad = fixture()
        pad['Standard'], pad['PadAngle'] = True, math.pi/2
        report = ConversionReport()
        result = parse(dumps(document, report=report)).one('/Library/Patterns/Pattern/Pads/Pad')
        self.assertFalse(result['Standard'])
        self.assertEqual((6, 3, 1.5708), tuple(result[n] for n in ('PadWidth_New', 'PadHeight_New', 'PadAngle')))
        self.assertTrue(pad['Standard'])
        self.assertEqual(['rotated-default-pad'], [n.rule for n in report.notices])
        self.assertFalse(report.warnings)

    def test_catalogue_keys_empty_blocks_and_optional_terminator(self):
        document = new_library('Examples')
        empty = dumps(document)
        self.assertIn('(Categories 0\n', empty)
        self.assertIn('(Patterns\n', empty)
        self.assertTrue(empty.endswith('\n()\n'))
        self.assertFalse(parse(empty).select('/Library/Patterns/Pattern'))
        category = document.one('/Library/Categories').add('Category', 'Assembly', 7)
        category.add('Type', 'Header', 12).add('Subtype', 'Through', 31)
        pattern = new_pattern('Example')
        document.one('/Library/Patterns').append(pattern)
        output = parse(dumps(document))
        self.assertEqual(('Through', 31), output.one('/Library/Categories/Category/Type/Subtype').values)

    def test_text_restrictions_warn_and_leave_authored_unicode_untouched(self):
        document = new_library('A "quoted" \u03a9')
        report = ConversionReport()
        output = parse(dumps(document, report=report))
        self.assertEqual('A !quoted! O', output.one('/Library')['Name'])
        self.assertEqual('A "quoted" \u03a9', document.one('/Library')['Name'])
        self.assertEqual({'asc-text-sanitization', 'asc-text-encoding'}, {n.rule for n in report.warnings})

    def test_pen_fallback_is_generated_context_and_invalid_widths_fail(self):
        document = read_binary((FIXTURES/'geometry.lib').read_bytes())
        shape = document.one('/Library/Patterns/Pattern/Shapes/Shape')
        shape['Width'] = -1
        syntax = loads_library(dumps(document, line_width=lambda layer: .9, report=ConversionReport()))
        header = syntax.one('/Library/Patterns/Pattern/Shapes/Shape[2]')
        self.assertEqual(.9, float(header.values[16]))
        self.assertEqual(-1, shape['Width'])
        for value in (None, True, -1, float('inf')):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'line width'):
                dumps(document, line_width=lambda layer: value, report=ConversionReport())

    def test_unknown_version_and_unmapped_data_fail_explicitly(self):
        report = ConversionReport()
        with self.assertRaises(UnsupportedFileError) as caught:
            dumps(new_library(), version=25, report=report)
        self.assertEqual(('pattern', 'asc', 25, 'version'),
            (caught.exception.family, caught.exception.format, caught.exception.version, caught.exception.reason))
        self.assertEqual(1, len(report.errors))
        document = new_library()
        document.one('/Library').add('UnknownData', 42)
        with self.assertRaises(NotImplementedError):
            dumps(document)


if __name__ == '__main__':
    unittest.main()
