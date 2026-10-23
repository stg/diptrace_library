"""Repeated public-format conversions must not accumulate geometric drift."""
from decimal import Decimal
import unittest

from lib.design import (new_schematic, parse_asc, parse_dch, parse_dchxml,
                        DchXmlExportContext)
from lib.design.schematic_objects import new_symbol, new_pin, new_symbol_shape, new_pattern_shape
from lib.design.schematic_refs import bind_schematic_references


def sample():
    document=new_schematic()
    part=document.one('/Schematic/Components').append(new_symbol('Amplifier','U1'))
    for name,value in (('X','17.0015'),('Y','-31.2345'),('Width','4.2501'),('Height','3.1251')):
        part.set_field(name,Decimal(value))
    part.set_field('Angle',90)
    pin=part.one('Pins').append(new_pin())
    pin.set_values(0,Decimal('-2.0005'),Decimal('.00025'))
    pin.set_field('Name','Input')
    pin.set_field('Length',Decimal('3.012345'))
    shape=part.one('Shapes').append(new_symbol_shape())
    shape.set_field('Type',2)
    for x,y in (('-2.0001','0'),('0','-2.0001'),('2.0001','0')):
        shape.one('Points_New').add('pt',Decimal(x),Decimal(y))
    bind_schematic_references(document)
    return document


def geometry(document):
    part=document.one('/Schematic/Components/Part')
    values=[part.scalar(name) for name in ('X','Y','Angle','Width','Height')]
    for pin in part.select('Pins/Pin'):
        values.extend((*pin.values[1:3],pin.scalar('Length'),pin.scalar('Orientation')))
    for shape in part.select('Shapes/Shape'):
        if shape.scalar('MarkingGenerated') not in (True,'Y'):
            values.extend(value for point in shape.select('Points_New/pt') for value in point.values)
    return tuple(Decimal(str(value)).quantize(Decimal('.0001')) for value in values)


class ConversionStabilityTests(unittest.TestCase):
    def test_binary_export_keeps_authored_footprint_coordinates_after_edit(self):
        current = new_schematic()
        part = current.one('/Schematic/Components').append(new_symbol('Box', 'U1'))
        pattern = part.one('Pattern')
        pattern.set_values('Footprint')
        pattern.set_field('Width', 10)
        pattern.set_field('Height', 6)
        drawing = pattern.one('Shapes').insert(new_pattern_shape(kind=1), 1)
        drawing.one('Points_New').add('pt', -2, -1)
        drawing.one('Points_New').add('pt', 2, 1)
        bind_schematic_references(current)
        current = parse_dch(current.to_dch_bytes())
        pattern = current.one('/Schematic/Components/Part/Pattern')
        pattern.one('Shapes/Shape[2]/Points_New').add('pt', 7, 9)
        output = parse_dch(current.to_dch_bytes())
        loaded = output.one('/Schematic/Components/Part/Pattern')
        self.assertEqual(loaded.select('Shapes/Shape[2]/Points_New/pt')[-1].values, (7, 9))
        self.assertEqual((loaded.scalar('OriginX'), loaded.scalar('OriginY')), (0, 0))
        self.assertEqual((loaded.scalar('Width'), loaded.scalar('Height')), (10, 6))

    def test_zero_angle_xml_keeps_rectangle_corner_order(self):
        current = new_schematic()
        part = current.one('/Schematic/Components').append(new_symbol('Box', 'U1'))
        shape = part.one('Shapes').append(new_symbol_shape())
        shape.set_field('Type', 4)
        for point in ((3, 6), (-6, -3)):
            shape.one('Points_New').add('pt', *point)
        bind_schematic_references(current)
        for _ in range(3):
            current = parse_dchxml(current.to_dchxml_bytes()).as_schematic()
            shape = current.one('/Schematic/Components/Part/Shapes/Shape')
            self.assertEqual([point.values for point in shape.select('Points_New/pt')], [(3, 6), (-6, -3)])

    def test_mixed_cycles_stabilize_at_binary_coordinate_precision(self):
        current=parse_dch(sample().to_dch_bytes())
        baseline=None
        for _ in range(5):
            current=parse_asc(current.to_asc_bytes().decode('cp1252')).as_schematic()
            current=parse_dchxml(current.to_dchxml_bytes()).as_schematic()
            current=parse_dch(current.to_dch_bytes())
            actual=geometry(current)
            if baseline is None:
                baseline=actual
            self.assertEqual(actual,baseline)
            self.assertEqual(current.references.issues,[])

    def test_xml_unit_cycles_do_not_move_authored_geometry(self):
        original=sample()
        expected=geometry(original)
        for units in ('mm','mil','inch'):
            current=original
            for _ in range(5):
                current=parse_dchxml(current.to_dchxml_bytes(
                    context=DchXmlExportContext(units=units))).as_schematic()
                self.assertEqual(geometry(current),expected,units)
                self.assertEqual(current.references.issues,[])
        self.assertEqual(geometry(original),expected)


if __name__=='__main__':
    unittest.main()
