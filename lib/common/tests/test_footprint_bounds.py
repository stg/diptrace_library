"""Independent physical envelopes remain stable under exact translations."""
from decimal import Decimal, localcontext
import math
import unittest

from lib.common.footprint_bounds import physical_bounds
from lib.common.footprint_objects import new_pad, new_pattern_drawing
from lib.common.geometry import Bounds, reflected_angle


def pad(kind=0, width=4, height=2, angle=0):
    result=new_pad('1')
    for name,value in dict(PadShape_New=kind,PadWidth_New=width,PadHeight_New=height,PadAngle=angle).items():
        result[name]=value
    return result


def drawing(kind, points):
    result=new_pattern_drawing(kind=kind)
    for point in points:
        result.one('Points_New').add('pt',*point)
    return result


class FootprintBoundsTests(unittest.TestCase):
    def test_reflected_asymmetric_envelope_is_exactly_the_mirrored_box(self):
        item = pad(2, width=Decimal('1.95'), height=Decimal('3.15'),
                   angle=Decimal('1.570785307179586'))
        item['X'], item['Y'] = Decimal('-3.5'), Decimal('.6')
        shape = drawing(2, ((4, -5), (5, 5)))
        box = physical_bounds(pads=(item,), drawings=(shape,))
        item['X'] = -item['X']
        item['PadAngle'] = reflected_angle(item['PadAngle'])
        for point in shape.select('Points_New/pt'):
            x, y = point.values
            point.set_values(-x, y)
        self.assertEqual(physical_bounds(pads=(item,), drawings=(shape,)),
                         Bounds(-box.right, box.top, -box.left, box.bottom))

    def test_circle_size_is_rotation_invariant_without_trigonometric_roundoff(self):
        size=Decimal('1.234567890123456789')
        for kind,corner in ((0,0),(1,0),(2,50)):
            item=pad(kind,width=size,height=size)
            item['PadCorner']=corner
            for degrees in range(360):
                item['PadAngle']=math.radians(degrees)
                box=physical_bounds(pads=(item,))
                self.assertEqual((box.width,box.height),(size,size))
        item=pad(0,width=size,height=Decimal('2.5'),angle=math.pi/2)
        box=physical_bounds(pads=(item,))
        self.assertEqual((box.width,box.height),(Decimal('2.5'),size))

    def test_rotated_ellipse_uses_its_analytic_extrema(self):
        item=pad(angle=math.pi/4)
        box=physical_bounds(pads=(item,))
        extent=math.sqrt(2.5)
        self.assertAlmostEqual(float(box.width),2*extent)
        self.assertAlmostEqual(float(box.height),2*extent)
        self.assertEqual(box.center,(0,0))

    def test_capsules_and_rounded_rectangles_include_their_curved_edges(self):
        for kind,corner,expected in ((1,0,1+math.sqrt(.5)),(2,25,math.sqrt(2)+.5)):
            with self.subTest(kind=kind):
                item=pad(kind,angle=math.pi/4)
                item['PadCorner']=corner
                box=physical_bounds(pads=(item,))
                self.assertAlmostEqual(float(box.right),expected)
                self.assertAlmostEqual(float(box.bottom),expected)
        item=pad(4,width=2,height=4,angle=math.pi/2)
        self.assertEqual(physical_bounds(pads=(item,)),Bounds(-2,-1,2,1))

    def test_polygon_and_copper_offset_rotate_about_the_pad_anchor(self):
        item=pad(3,angle=math.pi/2)
        item['X'],item['Y'],item['PadShape_X'],item['PadShape_Y']=10,20,3,4
        for point in ((0,0),(2,0),(1,1)):
            item.one('PadPoints_New').add('pt',*point)
        self.assertEqual(physical_bounds(pads=(item,)),Bounds(14,15,15,17))
        item['SurfacePad']=True
        self.assertEqual(physical_bounds(pads=(item,)),Bounds(10,18,11,20))

    def test_fiducial_bounds_ignore_angle_and_copper_offset(self):
        item=pad(20,width=2,height=4,angle=.3)
        item['PadShape_X'],item['PadShape_Y']=9,11
        self.assertEqual(physical_bounds(pads=(item,)),Bounds(-1,-2,1,2))

    def test_drawing_arcs_contribute_geometry_while_text_and_strokes_do_not(self):
        arc=drawing(6,((1,0),(0,1),(-1,0)))
        arc['Width']=100
        text=drawing(7,((1000,1000),))
        self.assertEqual(physical_bounds(drawings=(arc,text)),Bounds(-1,0,1,1))
        self.assertIsNone(physical_bounds(drawings=(text,)))

    def test_empty_copper_and_separate_holes_have_distinct_envelopes(self):
        for item in (pad(3),pad(5),pad(123)):
            with self.subTest(kind=item['PadShape_New']):
                self.assertIsNone(physical_bounds(pads=(item,)))
        self.assertEqual(physical_bounds(holes=((10,20,4),)),Bounds(8,18,12,22))
        with self.assertRaises(ValueError):
            physical_bounds(holes=((0,0,-1),))

    def test_small_geometry_at_large_coordinates_survives_low_decimal_precision(self):
        item=pad(3)
        item['X']=Decimal('1e100')
        for point in ((Decimal(0),Decimal(0)),(Decimal('1e-100'),Decimal('2e-100'))):
            item.one('PadPoints_New').add('pt',*point)
        with localcontext() as context:
            context.prec=3
            box=physical_bounds(pads=(item,))
            self.assertEqual(box.width,Decimal('1e-100'))
            self.assertEqual(box.height,Decimal('2e-100'))
            self.assertEqual(box.center[1],Decimal('1e-100'))

    def test_repeated_centering_is_stable_and_does_not_mutate_shape_settings(self):
        item=pad(2,angle=.3)
        item['X'],item['Y'],item['PadCorner']=Decimal('4.125'),Decimal('-3.75'),75
        shape=drawing(6,((7,1),(8,2),(9,1)))
        first=physical_bounds(pads=(item,),drawings=(shape,))
        cx,cy=first.center
        with localcontext() as context:
            context.prec=100
            item['X'],item['Y']=item['X']-cx,item['Y']-cy
            for row in shape.select('Points_New/pt'):
                row.set_values(Decimal(str(row.values[0]))-cx,Decimal(str(row.values[1]))-cy)
        second=physical_bounds(pads=(item,),drawings=(shape,))
        self.assertEqual(second.center,(0,0))
        self.assertEqual((second.width,second.height),(first.width,first.height))
        self.assertEqual(physical_bounds(pads=(item,),drawings=(shape,)),second)
        self.assertEqual(item['PadCorner'],75)


if __name__=='__main__':
    unittest.main()
