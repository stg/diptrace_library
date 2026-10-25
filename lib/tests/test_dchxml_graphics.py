"""Drawing units, picture data and identity links for dynamic net labels."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib import Document, Element, new_schematic, new_net, new_schematic_shape, parse_dchxml
from lib.schematic.formats.dchxml.graphics import (project_drawing)
from lib.common.units import XmlUnits
from lib.schematic.model.refs import (bind_schematic_references)


def drawing(kind):
    result = new_schematic_shape()
    for name, value in dict(Enabled=True, Selected=False, Type=kind, Page=0, PenWidth=1, Color=123,
        RelatedNet=-1, RelatedBus=-1, TextAngle=0, Picture_Width=6, Picture_Height=9, Picture_Proportions=False,
        TextHorz=-1, TextVert=-1, TextAlign=-1, Picture_Transparent=.5, VectorFont=True, FontSize=2,
        FontWidth=.2, FontScale=1, FontColor=123, LineSpacing=1.2, Group=-1, Locked=False,
        FontName='Tahoma', Picture_File='picture.png', Picture_File_Variable='').items():
        result.set_field(name, value)
    result.one('Points_New').add('pt', 3, 6)
    result.one('TextLine').add('pt', 'Hello')
    return result


class XmlGraphicsTests(unittest.TestCase):
    def test_picture_and_text_units_and_paths(self):
        units = XmlUnits('mm')
        picture = project_drawing(drawing(11), index=4, units=units)
        self.assertEqual((picture.scalar('PictureWidth'), picture.scalar('PictureHeight')), (2, 3))
        self.assertEqual((picture.scalar('HorzAlign'), picture.scalar('VertAlign')), ('Left', 'Top'))
        self.assertEqual(picture.one('PictureFile').scalar('Var'), 'picture.png')
        self.assertEqual(picture.one('Points/Point').scalar('Y'), -2)
        text = project_drawing(drawing(10), index=5, units=units)
        self.assertEqual(float(text.scalar('FontWidth')), .2)
        self.assertEqual(text.one('TextLines/TextLine').values, ('Hello',))
        self.assertEqual(text.one('FontName').values, ('Tahoma',))

    def test_schematic_width_omission_uses_its_own_threshold(self):
        source = drawing(1)
        for width, present in ((-2, False), (-1, False), (-.5, True), (0, True), (1, True)):
            source.set_field('PenWidth', width)
            projected = project_drawing(source, index=0, units=XmlUnits('mm'))
            self.assertEqual(projected.child('LineWidth') is not None, present)
            if present:
                self.assertAlmostEqual(float(projected.scalar('LineWidth')), width/3)

    def test_dynamic_net_label_follows_reordered_net_identity(self):
        document = new_schematic()
        schematic = document.one('/Schematic')
        nets = schematic.one('Nets')
        first, second = nets.append(new_net('A')), nets.append(new_net('B'))
        label = schematic.one('Shapes').append(drawing(10))
        label.set_field('RelatedNet', 0)
        bind_schematic_references(document)
        first.move_to(nets, 1)
        document.rebuild()
        self.assertEqual(label.scalar('RelatedNet'), 1)
        self.assertEqual(project_drawing(label, index=0, units=XmlUnits('mm')).scalar('NetId'), 1)

    def test_xml_net_and_bus_label_keys_are_numeric_and_follow_renaming(self):
        document = parse_dchxml('<Source Type="DipTrace-Schematic"><Schematic>'
            '<Nets><Net Id="7"/></Nets><Buses><Bus Id="9"/></Buses>'
            '<Shapes><Shape NetId="7" BusId="9"/></Shapes></Schematic></Source>')
        self.assertEqual(document.references.issues, [])
        document.one('/Source/Schematic/Nets/Net/Id').set_values(17)
        document.one('/Source/Schematic/Buses/Bus/Id').set_values(19)
        document.rebuild()
        label = document.one('/Source/Schematic/Shapes/Shape')
        self.assertEqual((label.scalar('NetId'), label.scalar('BusId')), (17, 19))


if __name__ == '__main__':
    unittest.main()
