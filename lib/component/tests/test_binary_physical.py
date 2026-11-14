"""Attached-footprint fields have an independent standalone revision gate."""
import unittest

from lib.common.binary_records import RecordWriter
from lib.common.footprint_codec import write_parameters, write_pattern_authoring
from lib.common.footprint_objects import new_pattern
from lib.common.model import Element
from lib.component.formats.eli.binary import ComponentError
from lib.component.formats.eli.physical import read_physical_parameters
from lib.component.formats.eli.reader import Reader
from lib.component.tests.test_binary_header import stream


def physical_payload(version):
    pattern = new_pattern('Example package')
    for name, value in dict(Width=18, Height=3, Spacing1=3.3, Spacing2=6.6,
            Number1=3, Number2=4, PadWidth=7.05, PadHeight=3.75,
            PadHole=.99, PadHoleH=1.32, PadHoleType=1, OriginX=.369,
            OriginY=-.702, OriginCross=False, OriginCircle=True,
            Name_Description='Physical control', Name_Unique='Example-package',
            Pattern_Manufacturer='Example maker', RecoveryCode='R1',
            PadCorner=12.5, PadShape_X=.33, PadShape_Y=-.66,
            TopMask_State=1, BotMask_State=2, TopPaste_State=3,
            PadMask_Percent=33, PadMask_EdgeGap=1.32).items():
        pattern[name] = value
    terminal = pattern.add('PadTerminal', 0)
    for name, value in dict(Type=2, X=.36, Y=-.69, Angle=.34,
            ShapeWidth=2.25, ShapeHeight=2.55, ShapeCorner=11).items():
        terminal.add(name, value)
    terminal.add('ShapePoints')
    pattern.one('PadMask_TopSegments').add('pt', .3, -.6, .9, -1.2)
    writer = RecordWriter()
    if version < 24:
        def text(value):
            encoded = value.encode('cp1252')
            writer.buffer.append(len(encoded))
            writer.buffer.extend(encoded)
        writer.text = text
    writer.integer(1)
    writer.integer(1)
    writer.integer(2)
    write_parameters(writer, pattern)
    writer.number(.45)
    writer.number(-.75)
    writer.integer(2)
    for number in (1.25, -2.5, 3.75, 4):
        writer.number(number)
    if version >= 27:
        write_pattern_authoring(writer, pattern)
    return pattern, bytes(writer.buffer)


class PhysicalParameterTests(unittest.TestCase):
    def test_base_fields_links_origins_and_exact_boundary(self):
        for version in (23, 24, 26, 27, 31, 33):
            with self.subTest(version=version):
                source, payload = physical_payload(version)
                reader = Reader(stream(version)+payload+b'end')
                part = Element('Part')
                result = read_physical_parameters(reader, Element('Component'), part)
                self.assertEqual('Example package', result['Name'])
                for name in ('Width', 'Height', 'Spacing1', 'Number2', 'PadHole', 'OriginY'):
                    self.assertEqual(source[name], result[name], name)
                self.assertEqual((1, 2), result.one('InternalConnections/IntCon').values)
                self.assertEqual((.45, -.75), (part['Origin_X'], part['Origin_Y']))
                self.assertEqual([(1.25, -2.5), (3.75, 4)],
                                 [point.values for point in result.select('PadPoints/pt')])
                self.assertEqual(b'end', reader.take(3))
                if version < 27:
                    self.assertIsNone(result.child('Name_Description'))
                    self.assertEqual([], result.children('PadTerminal'))
                else:
                    for name in ('OriginCross', 'Name_Description', 'Name_Unique',
                            'RecoveryCode', 'PadCorner', 'TopPaste_State', 'PadMask_Percent'):
                        self.assertEqual(source[name], result[name], name)
                    terminal = result.one('PadTerminal')
                    self.assertEqual((2, .36, -.69, .34, 11),
                        tuple(terminal[name] for name in ('Type', 'X', 'Y', 'Angle', 'ShapeCorner')))
                    self.assertEqual((.3, -.6, .9, -1.2),
                                     result.one('PadMask_TopSegments/pt').values)

    def test_each_truncated_boundary_rejects_without_reading_next_record(self):
        _, payload = physical_payload(27)
        for size in range(len(payload)):
            with self.subTest(size=size), self.assertRaises(ComponentError):
                read_physical_parameters(Reader(stream(27)+payload[:size]),
                                         Element('Component'), Element('Part'))


if __name__ == '__main__':
    unittest.main()
