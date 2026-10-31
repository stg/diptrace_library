"""Bottom-side XML frames remain stable under repeated format conversion."""
from decimal import Decimal
import math
import unittest

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.pcb.formats import io
from lib.pcb.formats.export_context import ExportContext
from lib.pcb.model.objects import new_document, new_component, new_pad, new_pattern_drawing
from lib.pcb.tests.test_component_projection import signature


class XmlFrameStabilityTests(unittest.TestCase):
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
