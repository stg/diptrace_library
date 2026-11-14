"""An independently authored library exercises the complete current ELI body."""
from pathlib import Path
import unittest

from lib.component.formats.eli.binary import ComponentError
from lib.component.formats.eli.decode import decode


FIXTURES = Path(__file__).with_name('fixtures')


class BinaryDecodeTests(unittest.TestCase):
    def test_component_and_attachment_keep_distinct_origins_and_names(self):
        result = decode((FIXTURES/'parameters.eli').read_bytes())
        self.assertEqual((33, 1, 'Component parameter controls'),
            (result.header.version, result.header.entry_count, result.header.name))
        part = result.root.one('Components/Component/Parts/Part')
        self.assertEqual(('Example component', 'U', 'Gate A', 'Control value'),
            tuple(part[name] for name in ('Name', 'RefDes', 'PartName', 'Value')))
        self.assertEqual((.45, -.75), (part['Origin_X'], part['Origin_Y']))
        self.assertEqual(('Example maker', 'https://example.invalid/device'),
            (part['Manufacturer'], part['Datasheet']))
        pattern = part.one('Pattern')
        self.assertEqual('Example package', pattern['Name'])
        self.assertEqual((.369, -.702), (pattern['OriginX'], pattern['OriginY']))
        self.assertEqual((7.05, 3.75, .99, 1.32, 12.5, 33),
            tuple(pattern[name] for name in ('PadWidth', 'PadHeight', 'PadHole',
                                             'PadHoleH', 'PadCorner', 'PadMask_Percent')))
        terminal = pattern.one('PadTerminal')
        self.assertEqual((.36, -.69, .34),
                         tuple(terminal[name] for name in ('X', 'Y', 'Angle')))
        self.assertEqual((.3, -.6, .9, -1.2), pattern.one('PadMask_TopSegments/pt').values)

    def test_fractional_fonts_links_and_model_vectors_reach_their_current_slots(self):
        part = decode((FIXTURES/'parameters.eli').read_bytes()).root.one(
            'Components/Component/Parts/Part')
        pins = part.select('Pins/Pin')
        self.assertEqual(['Input', 'Output'], [pin['Name'] for pin in pins])
        self.assertEqual([1, 2], [pin['Number'] for pin in pins])
        self.assertEqual([(3.25, True)]*2,
                         [(pin['NameFontSize'], pin['NameFontMono']) for pin in pins])
        pattern = part.one('Pattern')
        self.assertEqual([-1, 1, 2, -1],
                         [pad['Number_New'] for pad in pattern.select('Pads/Pad')])
        shape, = [shape for shape in pattern.select('Shapes/Shape') if shape['Type'] == 7]
        self.assertEqual((7.25, True, 2), (shape['FontSize'], shape['FontMono'], shape['PadId']))
        self.assertEqual(['First line', 'Second line'],
                         [line.values[0] for line in shape.select('TextLine/pt')])
        model = pattern.one('Model3D')
        self.assertEqual('example.step', model['Model3DFile'])
        self.assertEqual((11, 22, 33), tuple(model.one('Rotate')[axis] for axis in ('X', 'Y', 'Z')))
        self.assertEqual((13.2, -16.5, 19.8),
                         tuple(model.one('Offset')[axis] for axis in ('X', 'Y', 'Z')))
        self.assertTrue(model['KeepPins'])
        line = part.one('Shapes/Shape')
        self.assertEqual(.75, line['PenWidth'])
        self.assertEqual([(0, 0), (3, 0)], [point.values for point in line.select('Points_New/pt')])

    def test_truncated_body_and_unconsumed_suffix_are_rejected(self):
        data = (FIXTURES/'parameters.eli').read_bytes()
        for size in (1, 10, 100, 200, 400, 600, 800, 1000, 1200, 1500, 1800, len(data)-1):
            with self.subTest(size=size), self.assertRaises(ComponentError):
                decode(data[:size])
        with self.assertRaisesRegex(ComponentError, 'unconsumed library data'):
            decode(data+b'other data')


if __name__ == '__main__':
    unittest.main()
