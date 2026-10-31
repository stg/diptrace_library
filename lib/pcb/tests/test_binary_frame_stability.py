"""Half-quantum footprint frames stabilize at the binary format's precision."""
from decimal import Decimal
import math
import unittest

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.common.geometry import transform_point
from lib.pcb.formats import io
from lib.pcb.formats.capabilities import DIP
from lib.pcb.formats.dip.frame_projection import project_frames
from lib.pcb.formats.export_view import prepare_export
from lib.pcb.model.objects import (new_document, new_component, new_pad, new_pattern_drawing,
                                   new_net, new_point, new_trace, new_user_field)
from lib.pcb.tests.test_component_projection import signature


def rotated_design():
    document = new_document()
    component = document.one('/Board/Components').append(new_component('Device', 'U1'))
    component['Angle'] = Decimal(str(math.pi/4))
    component['RefDes_SilkAlign'] = 8
    component['RefDes_SilkX'], component['RefDes_SilkY'] = 3, 3
    pattern = component.one('Pattern')
    pad = pattern.one('Pads').append(new_pad('1', x=1, y=1))
    for name, value in dict(PadWidth_New=2, PadHeight_New=2, PadShape_New=2,
                            PadAngle=Decimal('.4'), SurfacePad=True).items():
        pad[name] = value
    shape = pattern.one('Shapes').append(new_pattern_drawing(kind=2))
    for point in ((2, 2), (3, 3)):
        shape.one('Points_New').add('pt', *point)
    return document


class BinaryFrameStabilityTests(unittest.TestCase):
    def test_rotated_fractional_envelope_keeps_placement_between_binary_saves(self):
        document = rotated_design()
        before = dumps(document, preserve=False)
        for version in DIP.write_versions:
            with self.subTest(version=version):
                def cycle(source):
                    return io.parse(io.serialize(source, format='dip', version=version,
                        report=ConversionReport()), report=ConversionReport())
                current = cycle(document)
                expected = signature(current.one('/Board/Components/Component'))
                for _ in range(4):
                    current = cycle(current)
                    actual = signature(current.one('/Board/Components/Component'))
                    self.assertEqual({name: (expected.get(name), actual.get(name))
                        for name in expected.keys() | actual.keys() if expected.get(name) != actual.get(name)}, {})
        self.assertEqual(dumps(document, preserve=False), before)

    def test_far_authored_origin_uses_a_representable_physical_anchor(self):
        document = rotated_design()
        component = document.one('/Board/Components/Component')
        component['X'] = 90000
        component.one('Pattern')['OriginX'] = 90000
        before = dumps(document, preserve=False)
        current = document
        for _ in range(5):
            current = io.parse(io.serialize(current, format='dip', version=62,
                report=ConversionReport()), report=ConversionReport())
            actual = signature(current.one('/Board/Components/Component'))
            if _:
                self.assertEqual(actual, expected)
            expected = actual
        self.assertEqual(dumps(document, preserve=False), before)

    def test_frame_projection_keeps_world_geometry_and_bound_targets(self):
        document = rotated_design()
        board = document.one('/Board')
        component = board.one('Components/Component')
        # Isolate frame translation from the format's angular quantization.
        component['Angle'] = Decimal('.7854')
        component['Name_SilkAlign'], component['Name_SilkX'] = 7, 23
        user = component.one('UserFields').append(new_user_field('Note', 'Authored'))
        user['SilkAlign'], user['SilkX'], user['SilkY'] = 8, 7, 8
        pattern = component.one('Pattern')
        pattern.one('Holes').add('Hole', True, False, 4, 5, 1, Decimal('.5'), -1)
        dimension = pattern.one('Dimensions').add('Dimension')
        for name, value in dict(Enabled=True, Locked=False, Type=0,
                Connected1=-1, Object1=0, SubObject1=0, Point1=0,
                Connected2=-1, Object2=0, SubObject2=0, Point2=0, Layer=2,
                X1=1, Y1=2, X2=3, Y2=4, XD=5, YD=6, ArrowSize=1, Units=0,
                VectorFont=True, FontName='', FontSize=2, FontScale=1,
                FontWidth=-1, ShowUnits=True, Angle=0, ExternalRadius=-1,
                PointerMode=0, PointerText='', Group=-1).items():
            dimension[name] = value
        net = board.one('Nets').append(new_net('SIGNAL'))
        pad = pattern.one('Pads/Pad')
        pad['Net'] = net
        trace = net.one('Traces').append(new_trace())
        for x in (10, 20):
            trace.one('Points').append(new_point(x=x, y=10, width=1))
        trace['Target1'] = pad
        before = dumps(document, preserve=False), tuple(document.references)
        view, _ = prepare_export(document, destination='dip', report=ConversionReport())
        component = view.one('/Board/Components/Component')

        def world_points():
            pattern = component.one('Pattern')
            dimension = pattern.one('Dimensions/Dimension')
            values = [(pattern['OriginX'], pattern['OriginY']),
                      (component['RefDes_SilkX'], component['RefDes_SilkY'])]
            values.extend((node['X'], node['Y']) for node in
                pattern.select('Pads/Pad') + pattern.select('Holes/Hole'))
            values.extend(row.values for row in pattern.select('Shapes/Shape/Points_New/pt'))
            values.extend((dimension['X'+end], dimension['Y'+end]) for end in ('1', '2', 'D'))
            values.extend((row['SilkX'], row['SilkY']) for row in component.select('UserFields/UserField'))
            return [transform_point(point, origin=(component['X'], component['Y']),
                                    angle=component['Angle']) for point in values]

        expected = world_points()
        fixed_offset = signature(component.one('Pattern/Model3D'))
        trace = view.one('/Board/Nets/Net/Traces/Trace')
        trace_geometry = [(point['X'], point['Y']) for point in trace.select('Points/Point')]
        project_frames(view.one('/Board'), report=ConversionReport())
        for actual, original in zip(world_points(), expected):
            for value, prior in zip(actual, original):
                self.assertAlmostEqual(value, prior, places=12)
        self.assertIs(trace['Target1'], component.one('Pattern/Pads/Pad'))
        self.assertIs(component.one('Pattern/Pads/Pad')['Net'], view.one('/Board/Nets/Net'))
        self.assertEqual([(point['X'], point['Y']) for point in trace.select('Points/Point')], trace_geometry)
        self.assertEqual(signature(component.one('Pattern/Model3D')), fixed_offset)
        self.assertEqual(component['Name_SilkX'], 23)
        self.assertEqual((dumps(document, preserve=False), tuple(document.references)), before)
        view.validate()

    def test_asymmetric_envelope_and_position_marking_do_not_walk_between_saves(self):
        document = new_document()
        component = document.one('/Board/Components').append(new_component('Device', 'U1'))
        component['RefDes_SilkAlign'] = 8
        component['RefDes_SilkX'] = Decimal('3.0001')
        pattern = component.one('Pattern')
        pad = pattern.one('Pads').append(new_pad('1', x=1))
        pad['PadWidth_New'], pad['PadHeight_New'], pad['PadShape_New'] = 2, 2, 2
        pad['SurfacePad'] = True
        shape = pattern.one('Shapes').append(new_pattern_drawing(kind=1))
        for point in ((2, 0), (Decimal('3.0001'), 0)):
            shape.one('Points_New').add('pt', *point)
        before = dumps(document, preserve=False)
        for version in DIP.write_versions:
            with self.subTest(version=version):
                def cycle(source):
                    return io.parse(io.serialize(source, format='dip', version=version,
                        report=ConversionReport()), report=ConversionReport())
                current = cycle(document)
                expected = signature(current.one('/Board/Components/Component'))
                for _ in range(4):
                    current = cycle(current)
                    self.assertEqual(signature(current.one('/Board/Components/Component')), expected)
                    current.validate()
        self.assertEqual(dumps(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
