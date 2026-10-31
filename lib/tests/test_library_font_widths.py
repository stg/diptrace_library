"""Schematic library XML uses physical strokes in the current dialect."""
from decimal import Decimal
import unittest
from xml.etree import ElementTree

from lib import ExportReport, new_schematic, parse
from lib.schematic.model.objects import new_symbol, new_pin, new_symbol_shape, new_pattern, new_pattern_shape


def design():
    document = new_schematic()
    slot = document.one('/Schematic/CacheLib/Slots').add('Slot',0,'')
    slot.add('VariablePath','')
    definition = slot.add('Definition',0)
    part = definition.append(new_symbol('Device','U',placed=False))
    pin = part.one('Pins').append(new_pin(placed=False))
    pin['Number'],pin['NameFontWidth'] = -1,Decimal('.6')
    shape = part.one('Shapes').append(new_symbol_shape())
    shape['Type'],shape['FontWidth'] = 10,Decimal('.6')
    shape.one('TextLine').add('pt','Symbol text')
    pattern = definition.append(new_pattern('Package'))
    shape = pattern.one('Shapes').insert(new_pattern_shape(1,kind=7),1)
    shape['FontWidth'] = Decimal('.6')
    shape.one('TextLine').add('pt','Footprint text')
    root = ElementTree.fromstring(document.to_dchxml_bytes(version=52,report=ExportReport()))
    pattern = root.find('Library/Library/Patterns/Pattern')
    ElementTree.SubElement(ElementTree.SubElement(pattern,'Dimensions'),'Dimension',
                           dict(Connected1='None',Connected2='None',FontWidth='0.2'))
    return parse(ElementTree.tostring(root),format='dchxml')


class LibraryFontWidthTests(unittest.TestCase):
    def test_current_and_earlier_xml_strokes_reimport_to_the_same_model_length(self):
        document = design()
        for version,expected in ((51,Decimal('.6')),(52,Decimal('.2'))):
            with self.subTest(version=version):
                output = document.to_dchxml_bytes(version=version,report=ExportReport())
                root = ElementTree.fromstring(output)
                for path,field in (('Library/Components/Component/Part/Pins/Pin/NameFont','Width'),
                                   ('Library/Components/Component/Part/Shapes/Shape','FontWidth'),
                                   ('Library/Library/Patterns/Pattern/Shapes/Shape','FontWidth'),
                                   ('Library/Library/Patterns/Pattern/Dimensions/Dimension','FontWidth')):
                    self.assertEqual(Decimal(root.find(path).get(field)),expected)
                rebuilt = parse(output,format='dchxml')
                definition = rebuilt.one('/Schematic/CacheLib/Slots/Slot/Definition')
                for path,name in (('Part/Pins/Pin','NameFontWidth'),('Part/Shapes/Shape','FontWidth'),
                                  ('Pattern/Shapes/Shape[2]','FontWidth'),('Pattern/Dimensions/Dimension','FontWidth')):
                    self.assertEqual(definition.one(path)[name],Decimal('.6'))


if __name__ == '__main__':
    unittest.main()
