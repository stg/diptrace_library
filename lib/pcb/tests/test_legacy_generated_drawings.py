"""Older generated label placeholders must not become ordinary authored text."""
from types import SimpleNamespace
import unittest

from lib.common.model import Element
from lib.pcb.formats.dip.components import _graphics
from lib.pcb.formats.dip.geometry import expand_pattern_drawings
from lib.pcb.formats.dip.read import Reader
from lib.pcb.formats.dip.write_components import write_pattern_graphics
from lib.pcb.formats.dip.writer import Writer
from lib.pcb.model.objects import new_document,new_component,new_pattern_drawing


def decoded_drawings(version, *, cached=False):
    source=new_document()
    component=source.one('/Board/Components').append(new_component('Device','U1'))
    pattern=component.one('Pattern');pattern['Width'],pattern['Height']=2,4
    for kind,generated in ((7,True),(7,False),(1,True)):
        drawing=pattern.one('Shapes').append(new_pattern_drawing(kind=kind))
        drawing['MarkingGenerated']=generated
        drawing.one('TextLine').add('pt','U1')
        drawing.one('Points_New').add('pt',1,2)
    class FixtureWriter(Writer):
        def text(self,value):
            if version>=38:return super().text(value)
            raw=value.encode('cp1252');self.integer(len(raw));self.buffer.extend(raw)

    writer=FixtureWriter(54);writer.header()
    write_pattern_graphics(writer,pattern,drawings=pattern.select('Shapes/Shape'),holes=(),placed=True)
    data=bytearray(writer.buffer)
    data[8:11]=(1_000_000+version).to_bytes(3,'big')
    reader=Reader(bytes(data));owner=Element('Definition' if cached else 'Component')
    if not cached:owner.add('BottomSide',False)
    physical=owner.add('Pattern');physical.add('Width',2);physical.add('Height',4)
    drawings=_graphics(reader,physical,text_markers=not cached)
    if cached:
        components=()
        definitions=(SimpleNamespace(definition=owner,pattern_inputs=drawings),)
    else:
        components=(SimpleNamespace(component=owner,drawings=drawings),)
        definitions=()
    return SimpleNamespace(header=SimpleNamespace(version=version),
        upgrades=SimpleNamespace(components=components,cached_definitions=definitions)),physical,drawings


class LegacyGeneratedDrawingTests(unittest.TestCase):
    def test_placed_placeholder_is_cleared_only_before_current_geometry(self):
        for version in (31,46,47,62):
            with self.subTest(version=version):
                decoded,pattern,inputs=decoded_drawings(version)
                self.assertEqual([item.text_marker for item in inputs],[True,False,False])
                self.assertEqual([s['Type'] for s in pattern.select('Shapes/Shape')],[7,7,1])
                expand_pattern_drawings(decoded)
                self.assertEqual([s['Type'] for s in pattern.select('Shapes/Shape')],
                                 [0,7,1] if version<47 else [7,7,1])
                literal=pattern.select('Shapes/Shape')[1]
                self.assertEqual(literal.one('TextLine/pt').values,('U1',))
                self.assertEqual(literal['Type'],7)

    def test_cached_types_have_no_placed_generated_marker(self):
        for version in (31,46,47,62):
            with self.subTest(version=version):
                decoded,pattern,inputs=decoded_drawings(version,cached=True)
                self.assertEqual([item.text_marker for item in inputs],[False,False,False])
                expand_pattern_drawings(decoded)
                self.assertEqual([s['Type'] for s in pattern.select('Shapes/Shape')],[700,7,1])


if __name__=='__main__':unittest.main()
