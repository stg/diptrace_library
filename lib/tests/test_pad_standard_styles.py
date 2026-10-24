"""Independent pad choices and format-specific style reconstruction."""
import copy
import math
import unittest
import xml.etree.ElementTree as ET

from lib import ExportReport, new_schematic, parse, parse_dch
from lib.schematic.model.pads import (empty_pad)
from lib.schematic.model.objects import (new_symbol)
from lib.schematic.model.refs import (bind_schematic_references)


PATTERN = '/Schematic/Components/Part/Pattern'


def source():
    current = new_schematic()
    part = current.one('/Schematic/Components').append(new_symbol('Device', 'U1'))
    pattern = part.one('Pattern')
    pattern.set_values('Footprint')
    for name, value in (('Width', 10), ('Height', 6), ('PadWidth', 4), ('PadHeight', 2), ('PadShape', 2)):
        pattern.set_field(name, value)
    for index, x in ((1, -3), (2, 3)):
        pad = pattern.one('Pads').insert(empty_pad(index), index)
        pad.annotations.clear()
        pad.set_values(index, str(index), '', x, 0)
        for name, value in (('Number_New', index), ('PadWidth_New', 4), ('PadHeight_New', 2),
                            ('PadShape_New', 2), ('PadAngle', math.pi/2), ('Standard', index == 1)):
            pad.set_field(name, value)
    bind_schematic_references(current)
    return current


def pads(current):
    return current.select(PATTERN+'/Pads/Pad')[1:-1]


class PadStandardStyleTests(unittest.TestCase):
    def test_binary_keeps_both_choices_at_the_same_nonzero_angle(self):
        current = source()
        for _ in range(3):
            data = current.to_dch_bytes()
            current = parse_dch(data)
            self.assertEqual([pad.scalar('Standard') for pad in pads(current)], [True, False])
            for pad in pads(current):
                self.assertAlmostEqual(float(pad.scalar('PadAngle')), math.pi/2, places=4)
            self.assertEqual(current.to_dch_bytes(), data)

    def test_xml_uses_style_identity_even_when_the_style_contents_are_equal(self):
        root = ET.fromstring(source().to_dchxml_bytes())
        styles = root.find('Library/Library/PadStyles')
        pattern = root.find('Library/Library/Patterns/Pattern')
        default_name = pattern.find('DefPad').get('Style')
        original = next(style for style in styles if style.get('Name') == default_name)
        separate = copy.deepcopy(original)
        separate.set('Name', 'IndependentStyle')
        styles.append(separate)
        first, second = pattern.findall('Pads/Pad')
        first.set('Style', default_name)
        second.set('Style', 'IndependentStyle')
        current = parse(ET.tostring(root), format='dchxml')
        self.assertEqual([pad.scalar('Standard') for pad in pads(current)], [True, False])
        binary = parse_dch(current.to_dch_bytes(report=ExportReport()))
        self.assertEqual([pad.scalar('Standard') for pad in pads(binary)], [True, False])

    def test_default_style_and_independent_pad_side_both_survive_xml(self):
        current = source()
        pads(current)[0].set_field('Sided', True)
        report = ExportReport()
        loaded = parse(current.to_dchxml_bytes(report=report), format='dchxml')
        self.assertTrue(pads(loaded)[0].scalar('Standard'))
        self.assertTrue(pads(loaded)[0].scalar('Sided'))
        self.assertNotIn('pad-standard-style', {notice.rule for notice in report.notices})

    def test_ascii_angle_adaptation_is_info_and_keeps_the_authoring_choice(self):
        current = source()
        report = ExportReport()
        output = current.as_asc(report=report)
        self.assertEqual([pad.scalar('Standard') for pad in output.select(PATTERN+'/Pads/Pad')], ['N', 'N'])
        self.assertIn('pad-standard-orientation', {notice.rule for notice in report.infos})
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])
        self.assertEqual([pad.scalar('Standard') for pad in pads(current)], [True, False])

    def test_xml_keeps_an_explicit_style_distinct_from_an_equal_default(self):
        current = source()
        report = ExportReport()
        loaded = parse(current.to_dchxml_bytes(report=report), format='dchxml')
        self.assertEqual([pad.scalar('Standard') for pad in pads(loaded)], [True, False])
        self.assertNotIn('pad-standard-style', {notice.rule for notice in report.notices})
        self.assertEqual(report.warnings, [])

    def test_xml_reconstructs_the_choice_when_explicit_geometry_differs_from_default(self):
        current = source()
        pads(current)[0].set_field('PadWidth_New', 6)
        report = ExportReport()
        loaded = parse(current.to_dchxml_bytes(report=report), format='dchxml')
        self.assertEqual([pad.scalar('Standard') for pad in pads(loaded)], [False, False])
        self.assertIn('pad-standard-style', {notice.rule for notice in report.infos})
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])
        self.assertEqual([pad.scalar('Standard') for pad in pads(current)], [True, False])
        self.assertEqual([pad.scalar('PadWidth_New') for pad in pads(loaded)], [6, 4])


if __name__ == '__main__':
    unittest.main()
