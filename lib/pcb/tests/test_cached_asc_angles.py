"""PCB cached ASC headers use integer radians; the authoring angle stays whole."""
import unittest

from lib.common.conversion import ConversionReport
from lib.pcb.formats.asc.cache_projection import project_cache
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_cache_projection import design, reopen, signature


class CachedAscAngleTests(unittest.TestCase):
    def project(self, angle, *, kind=7):
        document = design()
        drawing = document.one('/Board/CacheLib/Slots/Slot/Definition/Pattern/Shapes/Shape')
        drawing['Type'], drawing['TextAngle'] = kind, angle
        before = signature(document.root)
        report = ConversionReport()
        output = project_cache(document.one('/Board'), report=report)
        headers = output.select('CacheLib/cl_Components/cl_Component/cl_Pattern/cl_Shapes/cl_Shape')
        self.assertEqual(len(headers), 3)
        self.assertEqual(signature(document.root), before)
        return document, drawing, headers[1], report

    def test_fractional_text_angle_is_adapted_and_warned_without_mutating_the_model(self):
        for angle, expected in ((.35, 0), (4.7124, 5), (-1.5, -2), (2.5, 2), (3.5, 4)):
            with self.subTest(angle=angle):
                document, drawing, header, report = self.project(angle)
                self.assertEqual(header.values[15], expected)
                self.assertIs(type(header.values[15]), int)
                warnings = [n for n in report.warnings if n.rule == 'cached-text-angle']
                self.assertEqual(len(warnings), 1)
                self.assertEqual(drawing['TextAngle'], angle)
                converted = reopen(document, report=ConversionReport())
                converted_drawing = converted.one('/Board/CacheLib/Slots/Slot/Definition/Pattern/Shapes/Shape')
                self.assertEqual(converted_drawing['TextAngle'], expected)

    def test_already_integral_angles_are_lossless_and_quiet(self):
        for angle in (-2147483648, -7, 0, 5, 2147483647):
            with self.subTest(angle=angle):
                _, _, header, report = self.project(angle)
                self.assertEqual(header.values[15], angle)
                self.assertFalse([n for n in report.notices if n.rule in
                                  ('cached-text-angle', 'cached-drawing-angle')])

    def test_unused_nontext_angle_normalization_is_information(self):
        _, drawing, header, report = self.project(.35, kind=2)
        self.assertEqual(header.values[15], 0)
        self.assertEqual(drawing['TextAngle'], .35)
        self.assertFalse([n for n in report.warnings if n.rule == 'cached-text-angle'])
        self.assertEqual(len([n for n in report.infos if n.rule == 'cached-drawing-angle']), 1)

    def test_out_of_range_header_integer_is_rejected(self):
        for angle in (-2147483649, 2147483648):
            with self.subTest(angle=angle), self.assertRaisesRegex(PcbError, 'angle'):
                self.project(angle)


if __name__ == '__main__':
    unittest.main()
