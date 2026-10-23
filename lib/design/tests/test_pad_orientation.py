"""Pad angles are authoritative; legacy orientation flags are output views."""
import math
import unittest

from lib.design import new_schematic, parse, parse_asc, parse_dch
from lib.design.asc_import_graphics import empty_pad
from lib.design.dch_binary import Cursor
from lib.design.schematic_objects import new_symbol
from lib.design.schematic_refs import bind_schematic_references


def sample(angle):
    document=new_schematic()
    part=document.one('/Schematic/Components').append(new_symbol('Device','U1'))
    part.one('Pattern').set_values('Footprint')
    pad=part.one('Pattern/Pads').insert(empty_pad(1),1)
    pad.annotations.clear()
    for name,value in (('Number_New',1),('PadAngle',angle),('PadWidth_New',4),('PadHeight_New',2),('PadShape_New',2)):
        pad.set_field(name,value)
    bind_schematic_references(document)
    return document,pad


def placed_pad(document):
    return document.one('/Schematic/Components/Part/Pattern/Pads/Pad[2]')


def standard_flag_offset(data,document):
    cursor=Cursor(data)
    cursor.pos=placed_pad(document).source.start
    for kind in ('boolean','integer','number','number','text','text',
                 'number','number','number','number','integer','boolean','integer'):
        getattr(cursor,kind)()
    return cursor.pos


class PadOrientationTests(unittest.TestCase):
    def test_binary_compatibility_flag_follows_current_angle_after_edits(self):
        source,pad=sample(0)
        for angle,expected in ((0,False),(math.pi/4,False),(math.pi/2,True),
                               (math.pi,False),(3*math.pi/2,True),(-math.pi/2,False),(5*math.pi/2,False)):
            with self.subTest(angle=angle):
                pad.one('PadAngle').set_values(angle)
                data=source.to_dch_bytes()
                loaded=parse_dch(data)
                current=placed_pad(loaded)
                self.assertEqual(data[current.source.start],expected)
                self.assertAlmostEqual(float(current.scalar('PadAngle')),angle,places=4)
                self.assertFalse(current.children('Inverted'))
                self.assertFalse(current.select('StoredData/LegacyInverted'))

    def test_each_format_loads_the_same_angle_without_legacy_orientation_state(self):
        source,_=sample(math.pi/4)
        for format in ('dch','asc','dchxml'):
            with self.subTest(format=format):
                loaded=parse(getattr(source,'to_'+format+'_bytes')(),format=format)
                current=placed_pad(loaded)
                self.assertAlmostEqual(float(current.scalar('PadAngle')),math.pi/4,places=4)
                self.assertFalse(current.children('Inverted'))

    def test_ascii_and_binary_have_distinct_generated_flags(self):
        source,pad=sample(math.pi/4)
        raw=parse_asc(source.to_asc_bytes().decode('cp1252'))
        public=raw.one('/Schematic/Components/Part/Pattern/Pads/Pad')
        self.assertEqual(public.scalar('Inverted'),'Y')
        data=source.to_dch_bytes()
        loaded=parse_dch(data)
        self.assertEqual(data[placed_pad(loaded).source.start],0)
        self.assertFalse(pad.children('Inverted'))

    def test_standard_choice_remains_independent_of_the_current_angle(self):
        source,_=sample(math.pi/4)
        data=source.to_dch_bytes()
        offset=standard_flag_offset(data,parse_dch(data))
        varied=data[:offset]+b'\x01'+data[offset+1:]
        current=parse_dch(varied)
        pad=placed_pad(current)
        self.assertTrue(pad.scalar('Standard'))
        self.assertFalse(pad.select('StoredData/DefaultGeometry'))
        self.assertEqual(pad.scalar('PadWidth_New'),4)
        self.assertEqual(pad.scalar('PadHeight_New'),2)
        generated=current.to_dch_bytes()
        self.assertEqual(generated[offset],1)
        self.assertEqual(parse_dch(generated).to_dch_bytes(),generated)

    def test_standard_choice_survives_angle_edits_without_a_shadow_value(self):
        source,pad=sample(0)
        pad.set_field('Standard',True)
        current=parse_dch(source.to_dch_bytes())
        loaded=placed_pad(current)
        self.assertTrue(loaded.scalar('Standard'))
        self.assertIsNone(loaded.child('StoredData'))
        loaded.set_field('PadAngle',math.pi/4)
        rotated = parse_dch(current.to_dch_bytes())
        self.assertTrue(placed_pad(rotated).scalar('Standard'))
        self.assertAlmostEqual(float(placed_pad(rotated).scalar('PadAngle')), math.pi/4, places=4)
        loaded.set_field('Standard',False)
        self.assertFalse(placed_pad(parse_dch(current.to_dch_bytes())).scalar('Standard'))


if __name__=='__main__':
    unittest.main()
