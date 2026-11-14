"""Physical text uses its font stroke; geometric pen slots are regenerated."""
from importlib import import_module
from pathlib import Path
import unittest

from lib.common.conversion import ConversionReport
from lib.pattern.tests.comparison import snapshot


class LibraryTextStrokeTests(unittest.TestCase):
    def test_canonical_text_inputs_consume_the_unused_geometry_pen(self):
        fixtures = Path(__file__).parents[1]/'pattern/tests/fixtures'
        api = import_module('lib.pattern.formats.io')
        for format in ('lib', 'asc', 'libxml'):
            with self.subTest(format=format):
                document = api.parse((fixtures/('text_stroke_26.'+format)).read_bytes())
                text = document.one('/Library/Patterns/Pattern/Shapes/Shape')
                self.assertNotIn('Width', text)
                self.assertAlmostEqual(.6, text['FontWidth'], delta=.00005)
                self.assertEqual('Control', text.one('TextLine/pt')['Text'])
                document.validate()

    def test_both_families_keep_real_line_strokes_and_export_from_a_detached_view(self):
        for family, native, xml in (('pattern', 'lib', 'libxml'), ('component', 'eli', 'elixml')):
            model = import_module(f'lib.{family}.model')
            api = import_module(f'lib.{family}.formats.io')
            document = model.new_library('Examples')
            if family == 'pattern':
                pattern = document.one('/Library/Patterns').append(model.new_pattern('Physical'))
                drawing = model.new_drawing
            else:
                component = document.one('/Library/Components').append(model.new_component('Example', 'U'))
                pattern = component.append(model.new_pattern('Physical'))
                drawing = model.new_pattern_drawing
            text = pattern.one('Shapes').append(drawing(kind=7))
            text['FontWidth'] = .6
            text.one('Points_New').add('pt', -3, 1.5)
            text.one('TextLine').add('pt', 'Control')
            self.assertNotIn('Width', text)
            line = pattern.one('Shapes').append(drawing(kind=1))
            line['Width'] = .9
            for point in ((-3, 0), (3, 0)):
                line.one('Points_New').add('pt', *point)
            # An explicitly supplied inactive slot is projected away, without
            # mutating the caller's current data during output adaptation.
            text['Width'] = 36
            before = snapshot(document)
            for format in (native, 'asc', xml):
                with self.subTest(family=family, format=format):
                    report = ConversionReport()
                    restored = api.parse(api.serialize(document, format=format, report=report))
                    shapes = restored.select('/Library/Patterns/Pattern/Shapes/Shape' if family == 'pattern'
                        else '/Library/Components/Component/Pattern/Shapes/Shape')
                    self.assertNotIn('Width', shapes[0])
                    self.assertAlmostEqual(.6, shapes[0]['FontWidth'], delta=1e-12)
                    self.assertAlmostEqual(.9, shapes[1]['Width'], delta=1e-12)
                    self.assertEqual(before, snapshot(document))
                    self.assertFalse(report.errors)
                    restored.validate()
