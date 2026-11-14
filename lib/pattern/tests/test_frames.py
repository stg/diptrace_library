"""Import frames preserve physical relationships without constraining live edits."""
from pathlib import Path
import unittest

from lib.common.asc import dumps
from lib.common.asc_library import loads_library_bytes
from lib.pattern.formats.asc.read import parse as read_asc
from lib.pattern.formats.lib.read import parse as read_binary
from lib.pattern.formats.libxml.read import parse as read_xml
from lib.common.unplaced_footprint_frame import normalize_frame
from lib.pattern.model import new_pattern, new_drawing

FIXTURES=Path(__file__).with_name('fixtures')


class PatternFrameTests(unittest.TestCase):
    def test_three_imports_share_a_physical_frame_and_attachment_meaning(self):
        for filename,read in (('geometry.lib',read_binary),('geometry.asc',read_asc),
                              ('geometry_input.libxml',read_xml)):
            with self.subTest(filename=filename):
                document=read((FIXTURES/filename).read_bytes())
                pattern=document.one('/Library/Patterns/Pattern')
                pads=pattern.select('Pads/Pad')
                self.assertEqual((15,13.5),(pattern['Width'],pattern['Height']))
                self.assertEqual((-4.5,.75),(pads[0]['X'],pads[0]['Y']))
                self.assertEqual((6,-6),(pads[1]['X']-pads[0]['X'],pads[1]['Y']-pads[0]['Y']))
                self.assertEqual((-7.5,6.75),(pattern['OriginX'],pattern['OriginY']))
                dimension=pattern.one('Dimensions/Dimension[1]')
                self.assertEqual((1,2),(dimension['SubObject1'],dimension['SubObject2']))
                document.validate()

    def test_asymmetric_import_rebases_origin_generated_model_and_text(self):
        syntax=loads_library_bytes((FIXTURES/'metadata.asc').read_bytes(),retain_source=False)
        pattern=syntax.one('/Library/Patterns/Pattern')
        pattern.one('Pads/Pad[1]/PadWidth_New').set_values(7)
        document=read_asc(dumps(syntax))
        pattern=document.one('/Library/Patterns/Pattern')
        self.assertEqual((18.5,3),(pattern['Width'],pattern['Height']))
        self.assertEqual((.25,0),(pattern['OriginX'],pattern['OriginY']))
        model=pattern.one('Model3D')
        self.assertEqual((3.55,-6.6),(model['IPC_XOff'],model['IPC_YOff']))
        self.assertEqual((13.2,-16.5,19.8),tuple(model.one('Offset')[k] for k in ('X','Y','Z')))
        self.assertEqual(-5.75,pattern.one('Pads/Pad[1]')['X'])
        # Stored text anchors participate in translation, but not body bounds.
        source=read_asc((FIXTURES/'metadata.asc').read_bytes())
        old=source.one('/Library/Patterns/Pattern/Shapes/Shape/Points_New/pt')
        new=pattern.one('Shapes/Shape/Points_New/pt')
        self.assertEqual((old['X']+.25,old['Y']),(new['X'],new['Y']))
        document.validate()

    def test_live_data_edits_are_not_implicitly_recentered(self):
        document=read_binary((FIXTURES/'metadata.lib').read_bytes())
        pattern=document.one('/Library/Patterns/Pattern')
        pattern.one('Pads/Pad[1]')['X']=10
        self.assertEqual(10,pattern.one('Pads/Pad[1]')['X'])
        self.assertEqual(18,pattern['Width'])
        view=document.clone()
        normalize_frame(view.one('/Library/Patterns/Pattern'))
        self.assertEqual(10,pattern.one('Pads/Pad[1]')['X'])
        self.assertNotEqual(18,view.one('/Library/Patterns/Pattern')['Width'])
        document.validate()
        view.validate()

    def test_repeated_frame_normalization_does_not_drift(self):
        document=read_xml((FIXTURES/'geometry_input.libxml').read_bytes())
        pattern=document.one('/Library/Patterns/Pattern')
        before=[(node.kind,node.values) for node in pattern.walk(include_self=True)]
        for _ in range(50):
            normalize_frame(pattern)
        self.assertEqual(before,[(node.kind,node.values) for node in pattern.walk(include_self=True)])
        document.validate()

    def test_empty_or_text_only_body_has_a_minimal_frame(self):
        pattern=new_pattern('Label')
        shape=new_drawing(kind=7)
        shape.one('Points_New').add('pt',100,200)
        pattern.one('Shapes').append(shape)
        normalize_frame(pattern)
        self.assertEqual((.0001,.0001),(pattern['Width'],pattern['Height']))
        self.assertEqual((100,200),shape.one('Points_New/pt').values)


if __name__=='__main__':
    unittest.main()
