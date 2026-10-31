"""Board XML projects drawing properties in their meaningful shape domains."""
import unittest
from xml.etree import ElementTree as ET

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.pcb.formats import io
from lib.pcb.tests.test_xml_board_output import design as dimension_design


PATH='/Board/Shapes/Shape[1]'


def design():
    document=dimension_design()
    # Shape-kind changes must respect dimension target compatibility. These
    # tests concern projection domains, so remove the fixture's attached rulers.
    for dimension in tuple(document.select('/Board/Dimensions/Dimension')):
        document.remove(dimension)
    return document


class XmlDrawingDomainTests(unittest.TestCase):
    def test_nontext_drawings_do_not_render_unused_font_or_text_data(self):
        for kind in (0,1,2,3,4,5,7,8,9):
            with self.subTest(kind=kind):
                document=design()
                shape=document.one(PATH)
                shape['Type'],shape['FontName']=kind,'Unused\ufffffont'
                shape.one('TextLine').add('pt','Unused\ufffftext')
                before=model_text(document,preserve=False)
                root=ET.fromstring(io.serialize(document,format='dipxml',version=62,report=ConversionReport()))
                target=root.find('Board/Shapes/Shape')
                self.assertIsNone(target.find('FontName'))
                self.assertIsNone(target.find('TextLines'))
                self.assertNotIn('FontSize',target.attrib)
                self.assertNotIn('FontWidth',target.attrib)
                self.assertEqual(model_text(document,preserve=False),before)
                current=io.parse(ET.tostring(root),report=ConversionReport())
                current.validate()

    def test_text_content_is_emitted_for_both_text_bearing_kinds(self):
        for kind in (6,10):
            with self.subTest(kind=kind):
                document=design()
                shape=document.one(PATH)
                shape['Type'],shape['FontName']=kind,'Example font'
                shape.one('TextLine').add('pt','Visible Ω')
                root=ET.fromstring(io.serialize(document,format='dipxml',version=62,report=ConversionReport()))
                target=root.find('Board/Shapes/Shape')
                self.assertEqual(target.findtext('FontName'),'Example font')
                self.assertIn('Visible Ω',[x.text for x in target.findall('TextLines/TextLine')])
                self.assertEqual('FontSize' in target.attrib,kind==6)
                self.assertIn('TextAlign',target.attrib)

    def test_invalid_active_text_remains_an_xml_error(self):
        document=design()
        shape=document.one(PATH)
        shape['Type'],shape['FontName']=6,'Active\ufffffont'
        before=model_text(document,preserve=False)
        with self.assertRaisesRegex(ValueError,'outside XML 1.0'):
            io.serialize(document,format='dipxml',version=62,report=ConversionReport())
        self.assertEqual(model_text(document,preserve=False),before)

    def test_picture_alignment_and_image_settings_remain_active(self):
        document=design()
        shape=document.one(PATH)
        shape['Type'],shape['TextHorz'],shape['TextVert']=7,-1,1
        shape['PictureWidth'],shape['PictureHeight']=9,6
        shape['PictureTransparent']=25
        shape['Picture_File']='example.png'
        root=ET.fromstring(io.serialize(document,format='dipxml',version=62,report=ConversionReport()))
        target=root.find('Board/Shapes/Shape')
        self.assertEqual((target.get('HorzAlign'),target.get('VertAlign')),('Left','Bottom'))
        self.assertEqual((target.get('PictureWidth'),target.get('PictureHeight')),('3','2'))
        self.assertEqual(target.get('PictureTransparent'),'25')
        self.assertEqual(target.findtext('PictureFile/Path'),'example.png')


if __name__=='__main__':
    unittest.main()
