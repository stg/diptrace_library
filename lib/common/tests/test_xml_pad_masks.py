"""Shared mask/paste input distinguishes a complete style from an overlay."""
from decimal import Decimal
import math
import unittest

from lib.common.footprint_objects import new_pad, new_pattern
from lib.common.footprint_records import PAD_STYLE
from lib.common.model import Element
from lib.common.units import XmlUnits
from lib.common.xml_records import XmlRecord
from lib.common.xml_pads import read_mask_paste, read_pad_style
from lib.common.xml_pad_output import project_mask_paste


def pad():
    result = new_pad('1')
    result['DisableTopMask'] = 2
    result['PadMask_EdgeGap'] = 7
    result['CustomSwell_New'] = 9
    result['CustomShrink_New'] = 8
    result.one('PadMask_TopSegments').add('pt', 1, 2, 3, 4)
    result.one('PadMask_BotSegments').add('pt', 5, 6, 7, 8)
    return result


class XmlPadMaskTests(unittest.TestCase):
    def test_style_output_keeps_inactive_segment_dimensions_and_lists(self):
        fields = ('PadMask_Percent', 'PadMask_EdgeGap', 'PadMask_SegmentGap', 'PadMask_SegmentSide')
        for factory in (lambda: new_pad('1'), lambda: new_pattern('Package')):
            for values in ((50, .9, .6, 3), (37, .33, .66, 2.31), (50, 0, 0, 0)):
                for units in ('mm', 'mil', 'inch'):
                    source, target = factory(), factory()
                    with self.subTest(kind=source.kind, values=values, units=units):
                        for name, value in zip(fields, values):
                            source[name] = value
                        source.one('PadMask_BotSegments').add('pt', 1, 2, 3, 4)
                        output = project_mask_paste(source, units=XmlUnits(units))
                        read_mask_paste(XmlRecord(output), target, units=XmlUnits(units))
                        for name, value in zip(fields, values):
                            self.assertAlmostEqual(target[name], value, delta=4*math.ulp(float(value)))
                        self.assertEqual(target['BotPaste_State'] if source.kind != 'Pad'
                                         else target['DisableBottomPaste'], 0)
                        for actual, expected in zip(target.one('PadMask_BotSegments/pt').values, (1, 2, 3, 4)):
                            self.assertAlmostEqual(actual, expected, delta=4*math.ulp(float(expected)))
                        # Scaling may move the first result by a floating step;
                        # repeated output must not keep moving the same settings.
                        stable = tuple(target[name] for name in fields)
                        stable_points = target.one('PadMask_BotSegments/pt').values
                        for _ in range(3):
                            output = project_mask_paste(target, units=XmlUnits(units))
                            target = factory()
                            read_mask_paste(XmlRecord(output), target, units=XmlUnits(units))
                            self.assertEqual(stable, tuple(target[name] for name in fields))
                            self.assertEqual(stable_points, target.one('PadMask_BotSegments/pt').values)

    def test_complete_output_clears_template_values_and_keeps_inactive_settings(self):
        source, target = new_pad('1'), pad()
        source['PadMask_SegmentSide'] = Decimal('.1524')
        source['PadMask_SegmentGap'] = Decimal('.0762')
        output = project_mask_paste(source, units=XmlUnits('mil'), complete=True)
        self.assertEqual(output['TopMask'], 'Common')
        self.assertEqual(output['Segment_Side'], 2)
        self.assertFalse(output.one('TopSegments').children())
        read_mask_paste(XmlRecord(output), target, units=XmlUnits('mil'), partial=True)
        self.assertEqual(target['DisableTopMask'], 0)
        self.assertEqual(target['CustomSwell_New'], -1000)
        self.assertEqual(target['CustomShrink_New'], -1000)
        self.assertEqual(target['PadMask_SegmentSide'], 0.1524)
        self.assertEqual(target['PadMask_SegmentGap'], .0762)
        self.assertFalse(target.one('PadMask_TopSegments').children())
        self.assertFalse(target.one('PadMask_BotSegments').children())

    def test_complete_output_keeps_both_segment_lists_and_axis_conversion(self):
        source, target = pad(), new_pad('1')
        source['DisableTopPaste'] = 3
        output = project_mask_paste(source, units=XmlUnits('mm'), complete=True)
        self.assertEqual(output['TopPaste'], 'Segments')
        self.assertAlmostEqual(output.one('TopSegments/Item')['Y1'], -2/3, delta=math.ulp(-2/3))
        read_mask_paste(XmlRecord(output), target, units=XmlUnits('mm'), partial=True)
        # One physical-unit projection may round at the last binary place.
        for name in ('PadMask_TopSegments', 'PadMask_BotSegments'):
            for actual, expected in zip(target.one(name+'/pt').values, source.one(name+'/pt').values):
                self.assertAlmostEqual(actual, expected, delta=2*math.ulp(float(expected)))
        self.assertEqual(target['DisableTopPaste'], 3)

    def test_segment_side_is_a_fractional_length_for_pads_patterns_and_styles(self):
        for result in (new_pad('1'), new_pattern('Package')):
            with self.subTest(kind=result.kind):
                source = Element('MaskPaste')
                source.add('Segment_Side', Decimal('.35'))
                read_mask_paste(XmlRecord(source), result, units=XmlUnits('mm'), partial=True)
                self.assertAlmostEqual(result['PadMask_SegmentSide'], 1.05, delta=2*math.ulp(1.05))
                result['PadMask_SegmentSide'] = Decimal('2.125')
                self.assertEqual(result['PadMask_SegmentSide'], Decimal('2.125'))
        source = Element('PadStyle')
        source.add('Name', 'Fine paste')
        stack = source.add('MainStack')
        stack.add('Width', 1)
        stack.add('Height', 2)
        source.add('MaskPaste').add('Segment_Side', Decimal('.35'))
        result = Element('PadStyle', 'Fine paste')
        for name in ('PadPoints', 'PadMask_TopSegments', 'PadMask_BotSegments'):
            result.add(name)
        read_pad_style(XmlRecord(source), result, units=XmlUnits('mm'))
        result.bind_schema(PAD_STYLE)
        self.assertAlmostEqual(result['PadMask_SegmentSide'], 1.05, delta=2*math.ulp(1.05))
        result['PadMask_SegmentSide'] = Decimal('2.125')
        self.assertEqual(result['PadMask_SegmentSide'], Decimal('2.125'))

    def test_partial_overlay_retains_omitted_states_dimensions_and_lists(self):
        result = pad()
        source = Element('MaskPaste')
        source.add('CustomSwell', Decimal('.2'))
        read_mask_paste(XmlRecord(source), result, units=XmlUnits('mm'), partial=True)
        self.assertEqual(result['DisableTopMask'], 2)
        self.assertEqual(result['PadMask_EdgeGap'], 7)
        self.assertAlmostEqual(result['CustomSwell_New'], 0.6, delta=2*math.ulp(.6))
        self.assertEqual(result['CustomShrink_New'], -1000)
        self.assertEqual(result.one('PadMask_TopSegments/pt').values, (1, 2, 3, 4))

    def test_explicit_common_and_empty_list_clear_only_the_named_overlay(self):
        result = pad()
        source = Element('MaskPaste')
        source.add('TopMask', 'Common')
        source.add('TopSegments')
        read_mask_paste(XmlRecord(source), result, units=XmlUnits('mm'), partial=True)
        self.assertEqual(result['DisableTopMask'], 0)
        self.assertEqual(result.one('PadMask_TopSegments').children(), [])
        self.assertEqual(result.one('PadMask_BotSegments/pt').values, (5, 6, 7, 8))

    def test_complete_style_keeps_its_existing_reset_conventions(self):
        result = pad()
        read_mask_paste(XmlRecord(Element('MaskPaste')), result, units=XmlUnits('mm'))
        self.assertEqual(result['DisableTopMask'], 0)
        self.assertEqual(result['PadMask_EdgeGap'], 0)
        self.assertEqual(result['CustomSwell_New'], -1000)
        self.assertEqual(result.one('PadMask_TopSegments').children(), [])

    def test_segment_percent_is_a_scalar_while_coordinates_and_gaps_are_lengths(self):
        result = pad()
        source = Element('MaskPaste')
        source.add('Segment_Percent', 25)
        source.add('Segment_Gap', Decimal('.3'))
        row = source.add('TopSegments').add('Item')
        for name, value in dict(X1=1, Y1=2, X2=3, Y2=4).items():
            row.add(name, value)
        read_mask_paste(XmlRecord(source), result, units=XmlUnits('mm'), partial=True)
        self.assertEqual(result['PadMask_Percent'], 25)
        self.assertAlmostEqual(result['PadMask_SegmentGap'], 0.9, delta=2*math.ulp(.9))
        self.assertEqual(result.one('PadMask_TopSegments/pt').values, (3, -6, 9, -12))


if __name__ == '__main__':
    unittest.main()
