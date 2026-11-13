"""Bottom-side XML frames remain stable under repeated format conversion."""
from decimal import Decimal
import math
import unittest
from xml.etree import ElementTree as ET

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.common.geometry import transform_point
from lib.pcb.formats import io
from lib.pcb.formats.export_context import ExportContext
from lib.pcb.model.objects import new_document, new_component, new_pad, new_pattern_drawing
from lib.pcb.tests.test_component_projection import signature


class XmlFrameStabilityTests(unittest.TestCase):
    def test_rounded_unit_input_keeps_mixed_pad_frames_stable(self):
        document = new_document()
        component = document.one('/Board/Components').append(new_component('Generated', 'U1'))
        component['X'], component['Y'] = 32, -16
        component['BottomSide'], component['Angle'] = True, 3.1416
        component['RefDes_SilkAlign'], component['RefDes_SilkY'] = 8, -3.1
        pattern = component.one('Pattern')
        pattern['Type'] = 5
        # A generic two-row package: 7.6 mm row spacing, 2.54 mm pitch,
        # 1.5 mm pads and a 5 by 20 mm body. Pad 1 is square.
        shared_per_mm = 3
        for side in range(2):
            for index in range(8):
                number = side*8+index+1
                pad = pattern.one('Pads').append(new_pad(str(number),
                    x=(1 if side == 0 else -1)*7.6/2*shared_per_mm,
                    y=(index-3.5)*2.54*shared_per_mm))
                for name, value in dict(PadShape_New=2 if number == 1 else 1,
                        PadWidth_New=1.5*shared_per_mm, PadHeight_New=1.5*shared_per_mm,
                        PadAngle=math.pi/2, SurfacePad=False,
                        PadHole=.8*shared_per_mm, PadCorner=0).items():
                    pad[name] = value
        shape = pattern.one('Shapes').append(new_pattern_drawing(kind=2))
        for point in ((-2.5*shared_per_mm, -10*shared_per_mm),
                      (2.5*shared_per_mm, 10*shared_per_mm)):
            shape.one('Points_New').add('pt', *point)

        # Author a valid lower-precision XML input. A rounded quarter turn
        # makes the square's envelope slightly wider than the circular pads.
        context = ExportContext(units='mil')
        xml = ET.fromstring(io.serialize(document, format='dipxml', version=62, context=context))
        lengths = {'X', 'Y', 'Width', 'Height', 'XOff', 'YOff', 'OriginX', 'OriginY'}
        for element in xml.iter():
            for name in element.attrib.keys() & lengths:
                element.set(name, format(float(element.attrib[name]), '.4f'))
            if element.tag == 'Pad' and 'Angle' in element.attrib:
                element.set('Angle', format(float(element.attrib['Angle']), '.4f'))
        current = io.parse(ET.tostring(xml), report=ConversionReport())

        def physical_pads(board):
            part = board.one('/Board/Components/Component')
            return [transform_point((pad['X'], pad['Y']),
                    origin=(part['X'], part['Y']), angle=part['Angle'])
                    for pad in part.select('Pattern/Pads/Pad')]

        original_pads = physical_pads(current)
        previous_signature = previous_bytes = None
        for cycle in range(6):
            before = dumps(current, preserve=False)
            data = io.serialize(current, format='dipxml', version=62, context=context)
            self.assertEqual(dumps(current, preserve=False), before)
            current = io.parse(data, report=ConversionReport())
            current.validate()
            actual = signature(current.one('/Board/Components/Component'))
            if cycle:
                self.assertEqual(actual, previous_signature)
                self.assertEqual(data, previous_bytes)
            pads = physical_pads(current)
            self.assertEqual(len(pads), len(original_pads))
            for actual_pad, original_pad in zip(pads, original_pads):
                for actual_coordinate, original_coordinate in zip(actual_pad, original_pad):
                    # Unit projection, two rotation products, their sum and
                    # placement translation each contribute floating rounding.
                    self.assertLessEqual(abs(actual_coordinate-original_coordinate),
                                         8*math.ulp(float(original_coordinate)))
            previous_signature, previous_bytes = actual, data

    def test_shallow_arcs_do_not_feed_roundoff_back_into_placement(self):
        for bottom in (False, True):
            for units in ('mm', 'mil', 'inch'):
                for angle in (0, .7, 1.5708):
                    with self.subTest(bottom=bottom, units=units, angle=angle):
                        document = new_document()
                        component = document.one('/Board/Components').append(new_component('Device', 'U1'))
                        component['BottomSide'], component['Angle'] = bottom, angle
                        component['RefDes_SilkAlign'], component['RefDes_SilkY'] = 8, -3.1
                        # The arcs have equal vertical extrema and slightly
                        # different curvatures. Recomputing their circles and
                        # converting units can leave a last-bit center residue.
                        for points in (((-5.1, -1.1), (0, -2.9), (5.1, -1.1)),
                                       ((5.1, 1.101), (0, 2.9), (-5.1, 1.101))):
                            shape = component.one('Pattern/Shapes').append(new_pattern_drawing(kind=6))
                            for point in points:
                                shape.one('Points_New').add('pt', *point)
                        before = dumps(document, preserve=False)
                        current, expected, previous_bytes = document, None, None
                        for cycle in range(6):
                            data = io.serialize(current, format='dipxml', version=62,
                                context=ExportContext(units=units), report=ConversionReport())
                            current = io.parse(data, report=ConversionReport())
                            current.validate()
                            actual = signature(current.one('/Board/Components/Component'))
                            if cycle:
                                self.assertEqual(actual, expected)
                            if cycle > 1:
                                self.assertEqual(data, previous_bytes)
                            expected, previous_bytes = actual, data
                        self.assertEqual(dumps(document, preserve=False), before)

    def test_long_local_coordinates_keep_their_centered_frame_between_saves(self):
        for bottom in (False, True):
            for units in ('mm', 'mil', 'inch'):
                with self.subTest(bottom=bottom, units=units):
                    document = new_document()
                    component = document.one('/Board/Components').append(new_component('Device', 'U1'))
                    component['BottomSide'], component['Angle'] = bottom, Decimal('.7')
                    pattern = component.one('Pattern')
                    pad = pattern.one('Pads').append(new_pad('1',
                        x=Decimal('-3.123456789012345678901234567'), y=Decimal('.6')))
                    for name, value in dict(PadShape_New=2, PadWidth_New=Decimal('1.95'),
                            PadHeight_New=Decimal('3.15'), PadAngle=Decimal('.3'), SurfacePad=True).items():
                        pad[name] = value
                    shape = pattern.one('Shapes').append(new_pattern_drawing(kind=2))
                    for point in ((4, -5), (5, 5)):
                        shape.one('Points_New').add('pt', *point)
                    before = dumps(document, preserve=False)
                    def cycle(source):
                        return io.parse(io.serialize(source, format='dipxml', version=62,
                            context=ExportContext(units=units), report=ConversionReport()), report=ConversionReport())
                    current = cycle(document)
                    expected = signature(current.one('/Board/Components/Component'))
                    for _ in range(4):
                        current = cycle(current)
                        self.assertEqual(signature(current.one('/Board/Components/Component')), expected)
                        current.validate()
                    self.assertEqual(dumps(document, preserve=False), before)

    def test_asymmetric_pad_and_drawing_repeat_without_placement_residue(self):
        for angle in (Decimal('.3'), Decimal('1.570785307179586'),
                      Decimal(str(math.pi/2)), Decimal(str(3*math.pi/2))):
            for units in ('mm', 'mil', 'inch'):
                with self.subTest(angle=angle, units=units):
                    document = new_document()
                    component = document.one('/Board/Components').append(new_component('Device', 'U1'))
                    component['X'], component['Y'], component['Angle'] = 12, 18, Decimal('.7')
                    component['BottomSide'] = True
                    pattern = component.one('Pattern')
                    pad = pattern.one('Pads').append(new_pad('1', x=Decimal('-3.5'), y=Decimal('.6')))
                    for name, value in dict(PadShape_New=2, PadWidth_New=Decimal('1.95'),
                                            PadHeight_New=Decimal('3.15'), PadAngle=angle, SurfacePad=True).items():
                        pad[name] = value
                    shape = pattern.one('Shapes').append(new_pattern_drawing(kind=2))
                    for point in ((4, -5), (5, 5)):
                        shape.one('Points_New').add('pt', *point)
                    before = dumps(document, preserve=False)
                    def cycle(source):
                        data = io.serialize(source, format='dipxml', version=62,
                            context=ExportContext(units=units), report=ConversionReport())
                        return io.parse(data, report=ConversionReport())
                    current = cycle(document)
                    expected = signature(current.one('/Board/Components/Component'))
                    for _ in range(4):
                        current = cycle(current)
                        self.assertEqual(signature(current.one('/Board/Components/Component')), expected)
                        current.validate()
                    self.assertEqual(dumps(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
