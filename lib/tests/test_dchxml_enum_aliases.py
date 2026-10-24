"""Named XML aliases keep their meaning through shared and binary conversion."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib import ExportReport, new_schematic, parse_dch, parse_dchxml
from lib.schematic.model.objects import (new_pattern_shape, new_symbol, new_symbol_shape)
from lib.schematic.model.refs import (bind_schematic_references)


def label_document(value=-1):
    document = new_schematic()
    part = document.one('/Schematic/Components').append(new_symbol('Label', 'U1'))
    pattern = part.one('Pattern')
    pattern.set_values('Footprint')
    pattern.set_field('Width', 12)
    pattern.set_field('Height', 6)
    pattern.one('Model3D').set_field('Units', value)
    for owner, shape, kind in ((part.one('Shapes'), new_symbol_shape(), 10),
                               (pattern.one('Shapes'), new_pattern_shape(), 7)):
        shape.set_field('Type', kind)
        for name in ('TextHorz', 'TextVert', 'TextAlign'):
            shape.set_field(name, value)
        shape.one('TextLine').add('pt', 'label')
        shape.one('Points_New').add('pt', 0, 0)
        owner.insert(shape, 1) if kind == 7 else owner.append(shape)
    for name in ('ShowRefDes', 'ShowValue'):
        marking = part.one(name)
        values = list(marking.values)
        values[-5:-3] = [value, value]
        marking.set_values(*values)
    bind_schematic_references(document)
    return document


class XmlEnumAliasTests(unittest.TestCase):
    def assert_label_states(self, document, value, *, model_units=None):
        part = document.one('/Schematic/Components/Part')
        self.assertEqual(part.one('Pattern/Model3D').scalar('Units'), value if model_units is None else model_units)
        for path in ('Shapes/Shape', 'Pattern/Shapes/Shape'):
            labels = [shape for shape in part.select(path)
                      if [line.values for line in shape.select('TextLine/pt')] == [('label',)]]
            self.assertEqual(len(labels), 1)
            for name in ('TextHorz', 'TextVert', 'TextAlign'):
                self.assertEqual(labels[0].scalar(name), value)
        for name in ('ShowRefDes', 'ShowValue'):
            self.assertEqual(part.one(name).values[-5:-3], (value, value))

    def test_named_aliases_survive_repeated_xml_and_binary_conversion(self):
        source = label_document()
        before = source.to_dch_bytes()
        document = source
        for _ in range(3):
            raw = parse_dchxml(document.to_dchxml_bytes(report=ExportReport()))
            original_xml = raw.to_dchxml_bytes()
            document = raw.as_schematic()
            self.assert_label_states(document, -1)
            self.assertEqual(raw.to_dchxml_bytes(), original_xml)
            document = parse_dch(document.to_dch_bytes(report=ExportReport()))
            self.assert_label_states(document, -1)
        self.assertEqual(source.to_dch_bytes(), before)

    def test_equivalent_numeric_aliases_modernize_like_named_labels(self):
        source = label_document(2)
        model = source.one('/Schematic/Components/Part/Pattern/Model3D')
        model.set_field('Units', 3)
        raw = source.as_dchxml(report=ExportReport())
        named = raw.as_schematic()
        self.assert_label_states(named, -1)
        self.assertEqual(model.scalar('Units'), 3)
        for node in raw.root.walk():
            if node.kind == 'Units' and node.values == ('Wings',):
                node.set_values(3)
            if node.kind in ('HorzAlign', 'VertAlign', 'TextAlign', 'Horz', 'Vert'):
                if node.values in (('Left',), ('Top',)):
                    node.set_values(2)
        numeric = raw.as_schematic()
        self.assert_label_states(numeric, -1)
        self.assert_label_states(parse_dch(numeric.to_dch_bytes(report=ExportReport())), -1)
        for _ in range(3):
            numeric = numeric.as_dchxml(report=ExportReport()).as_schematic()
            self.assert_label_states(numeric, -1)

    def test_other_numeric_values_and_separate_enum_domains_remain_unchanged(self):
        from lib.schematic.formats.dchxml.import_values import (enum_value)
        for value in (-3, -1, 0, 1, 3, 777):
            self.assertEqual(enum_value(value, ('Center', 'Right', 'Left'), negative='Left'), value)
        self.assertEqual(enum_value(2, ('Left', 'Center', 'Right')), 2)
        self.assertEqual(enum_value('Left', ('Left', 'Center', 'Right')), 0)
        self.assertEqual(enum_value(4, ('Pin', 'Wire', '2', 'Bus', 'Free')), 4)

    def test_schematic_drawing_aliases_have_the_same_shared_meaning(self):
        text = new_schematic().to_dchxml()
        drawings = '''<Shapes><Shape Id="0" Type="Text" Sheet="0"
            HorzAlign="Left" VertAlign="Top" TextAlign="Left">
            <Points><Point X="1" Y="2"/></Points>
            <TextLines><TextLine>label</TextLine></TextLines>
            </Shape></Shapes>'''
        raw = parse_dchxml(text.replace('</Schematic>', drawings+'</Schematic>'))
        document = raw.as_schematic()
        shape = document.one('/Schematic/Shapes/Shape')
        self.assertEqual(tuple(shape.scalar(name) for name in ('TextHorz', 'TextVert', 'TextAlign')), (-1, -1, -1))
        binary = parse_dch(document.to_dch_bytes(report=ExportReport()))
        projected = binary.as_dchxml().one('/Source/Schematic/Shapes/Shape')
        self.assertEqual(tuple(projected.scalar(name) for name in ('HorzAlign', 'VertAlign', 'TextAlign')),
                         ('Left', 'Top', 'Left'))


if __name__ == '__main__':
    unittest.main()
