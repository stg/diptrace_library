"""Field-bound text keeps authored geometry and follows current component data."""
import unittest
import xml.etree.ElementTree as ET

from lib.design import ExportReport, Index, ReferenceError, new_schematic, parse
from lib.design.schematic_objects import new_symbol, new_symbol_shape
from lib.design.schematic_refs import bind_schematic_references
from lib.design.symbol_text import refresh_symbol_text

PART = '/Schematic/Components/Part'


def source():
    doc = new_schematic()
    part = doc.one('/Schematic/Components').append(new_symbol('Buffer', 'U42'))
    for name, value in dict(Width=10, Height=6, Value='Value', PartName='Gate A',
                            PartDescriptor='B', Manufacturer='Maker', Datasheet='Data', AllowParts=True).items():
        part.set_field(name, value)
    part.set_field('ShowName', 1, 1, 7, 0, 0, 0, 0, 0)
    part.set_field('ShowRefDes', 1, 1, 7, 0, 0, 0, 0, 0)
    part.one('UserFields').add('UserField', 'Code', 'ABC', 0, 1, 7, 0, 0, 0, 0, 0)
    for kind in (*range(8), 20):
        shape = part.one('Shapes').append(new_symbol_shape())
        for name, value in dict(Type=10, FontType=kind, FontColor=123456, Locked=True,
                                LineSpacing=2.5, TextAlign=1).items():
            shape.set_field(name, value)
        shape.one('Points_New').add('pt', 3, -4)
        shape.one('TextLine').add('pt', 'Sentinel')
    bind_schematic_references(doc)
    return doc


def texts(doc):
    return {shape.scalar('FontType'): [row.values[0] for row in shape.select('TextLine/pt')]
            for shape in doc.select(PART+'/Shapes/Shape') if not shape.scalar('MarkingGenerated')}


class SymbolTextTests(unittest.TestCase):
    def test_common_global_suffix_choices_modernize_without_changing_instance_inheritance(self):
        doc = source()
        part = doc.one(PART)
        for name in ('Name', 'RefDes'):
            part.set_field('Show'+name, 1, 0, 7, 0, 0, 0, 0, 0)
            doc.one('/Schematic').set_field('Show'+name+'_Global', 1, 0, 7)
        refresh_symbol_text(doc)
        self.assertEqual(texts(doc)[1], ['Buffer'])
        self.assertEqual(texts(doc)[2], ['U42.B'])
        self.assertEqual(part.one('ShowRefDes').values[1], 0)
        self.assertEqual(doc.one('/Schematic/ShowRefDes_Global').values[1], 1)
        self.assertEqual(doc.one('/Schematic/ShowName_Global').values[1], 2)

    def test_generated_labels_keep_the_regenerator_suffix_decision(self):
        doc = new_schematic()
        part = doc.one('/Schematic/Components').append(new_symbol('Buffer', 'U1'))
        part.set_field('PartDescriptor', 'A')
        part.set_field('AllowParts', False)
        part.set_field('ShowRefDes', 1, 1, 7, 0, 0, 0, 0, 0)
        bind_schematic_references(doc)
        loaded = parse(doc.to_dch_bytes(), format='dch')
        shape = next(s for s in loaded.select(PART+'/Shapes/Shape') if s.scalar('FontType') == 2)
        self.assertFalse(shape.scalar('ShowPart'))
        self.assertEqual(shape.one('TextLine/pt').values, ('U1',))

    def test_known_bindings_refresh_without_replacing_drawings_or_appearance(self):
        doc = source()
        shapes = doc.select(PART+'/Shapes/Shape')
        rows = [s.one('TextLine/pt') for s in shapes]
        self.assertEqual(len(refresh_symbol_text(doc)), 7)
        self.assertEqual(texts(doc), {0:['Sentinel'], 1:['Buffer (Gate A)'], 2:['U42.B'],
                         3:['Value'], 4:['Gate A'], 5:['Maker'], 6:['Data'], 7:['Sentinel'], 20:['ABC']})
        self.assertEqual(doc.select(PART+'/Shapes/Shape'), shapes)
        self.assertEqual([s.one('TextLine/pt') for s in shapes], rows)
        for shape in shapes:
            self.assertEqual(shape.one('Points_New/pt').values, (3, -4))
            self.assertEqual((shape.scalar('FontColor'), shape.scalar('LineSpacing'), shape.scalar('Locked')),
                             (123456, 2.5, True))
        self.assertEqual(refresh_symbol_text(doc), ())

    def test_suffix_choices_follow_common_settings_and_require_enabled_parts(self):
        doc = source()
        part = doc.one(PART)
        part.set_field('ShowName', 1, 0, 7, 0, 0, 0, 0, 0)
        doc.one('/Schematic').set_field('ShowName_Global', 1, 1, 7)
        for allow, suffix in ((True, ' (Gate A)'), (False, '')):
            part.set_field('AllowParts', allow)
            refresh_symbol_text(doc)
            self.assertEqual(texts(doc)[1], ['Buffer'+suffix])
        part.set_field('Enabled', False)
        part.set_argument(0, 'Changed')
        self.assertEqual(refresh_symbol_text(doc), ())
        self.assertEqual(texts(doc)[1], ['Buffer'])

    def test_xml_import_resolves_template_text_and_future_edits_drive_every_writer(self):
        doc = source()
        xml = ET.fromstring(doc.to_dchxml_bytes(report=ExportReport()))
        for shape in xml.findall('.//Library/Components/Component/Part/Shapes/Shape'):
            for line in shape.findall('Lines/Item'):
                line.text = 'Obsolete template text'
        current = parse(ET.tostring(xml), format='dchxml')
        self.assertEqual(texts(current)[2], ['U42.B'])
        self.assertEqual(texts(current)[4], ['Gate A'])
        self.assertEqual(texts(current)[0], ['Obsolete template text'])
        current.one(PART).set_argument(1, 'U99')
        current.one(PART+'/UserFields/UserField').set_argument(1, 'DEF')
        before = [(node.kind, node.values) for node in current.root.walk()]
        for kind in ('dch', 'asc', 'dchxml'):
            loaded = parse(getattr(current, 'to_'+kind+'_bytes')(report=ExportReport()), format=kind)
            self.assertEqual(texts(loaded)[2], ['U99.B'])
            self.assertEqual(texts(loaded)[20], ['DEF'])
            for point in loaded.select(PART+'/Shapes/Shape/Points_New/pt'):
                self.assertAlmostEqual(float(point.values[0]), 3, places=12)
                self.assertAlmostEqual(float(point.values[1]), -4, places=12)
        self.assertEqual([(node.kind, node.values) for node in current.root.walk()], before)

    def test_redundant_text_rows_cannot_remove_a_referenced_identity(self):
        doc = source()
        shape = doc.select(PART+'/Shapes/Shape')[1]
        extra = shape.one('TextLine').add('pt', 'Extra')
        field = doc.root.add('Selection', 1)
        reference = doc.references.bind(field, extra, Index(field))
        doc.one('/Schematic/ShowRefDes_Global').set_argument(1, 0)
        before = [(node.kind, node.values) for node in doc.root.walk()]
        with self.assertRaises(ReferenceError):
            refresh_symbol_text(doc)
        self.assertEqual([(node.kind, node.values) for node in doc.root.walk()], before)
        self.assertIs(reference.target, extra)


if __name__ == '__main__':
    unittest.main()
