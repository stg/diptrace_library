"""Standalone ASC uses the same owned objects and graph as binary/XML input."""
from pathlib import Path
import unittest

from lib.common.errors import UnsupportedFileError
from lib.pattern.formats.asc.read import parse
from lib.pattern.formats.asc.write import project_document
from lib.pattern.formats.asc.syntax import dumps as render
from lib.pattern.model import new_library, new_pattern


FIXTURES = Path(__file__).with_name('fixtures')


class PatternAscReadTests(unittest.TestCase):
    def test_current_default_contour_replaces_the_legacy_projection(self):
        for points in ((), ((-2, -1), (3, -1), (0, 4))):
            with self.subTest(points=points):
                document = new_library()
                document.one('/Library/Patterns').append(new_pattern('Example'))
                syntax = project_document(document)
                pattern = syntax.one('/Library/Patterns/Pattern')
                pattern.one('PadShape_New').set_values(3)
                pattern.one('PadPoints').add('pt', 99, 98)
                current = pattern.add('PadPoints_New')
                for point in points:
                    current.add('pt', *point)
                restored = parse(render(syntax)).one('/Library/Patterns/Pattern')
                self.assertEqual(points, tuple(p.values for p in restored.select('PadPoints/pt')))
                self.assertIsNone(restored.child('PadPoints_New'))

    def test_default_contour_without_a_newer_projection_remains_authored(self):
        document = new_library()
        pattern = document.one('/Library/Patterns').append(new_pattern('Example'))
        pattern['PadShape'] = 3
        points = ((-2, -1), (3, -1), (0, 4))
        for point in points:
            pattern.one('PadPoints').add('pt', *point)
        restored = parse(render(project_document(document))).one('/Library/Patterns/Pattern')
        self.assertEqual(points, tuple(p.values for p in restored.select('PadPoints/pt')))

    def test_geometry_and_attachments_are_editable_identities(self):
        document = parse((FIXTURES/'geometry.asc').read_bytes())
        pattern = document.one('/Library/Patterns/Pattern')
        self.assertEqual(('Example footprint','R','Example value'),
                         tuple(pattern[name] for name in ('Name','RefDes','Value')))
        pads = pattern.select('Pads/Pad')
        self.assertEqual(2,len(pads))
        self.assertEqual((-4.5,0.75),(pads[0]['X'],pads[0]['Y']))
        self.assertIs(pattern.one('Pattern_Groups/pt'),pads[0]['Group'])
        self.assertEqual([],pattern.one('Shapes/Shape').select('TextLine/pt'))
        dimension = pattern.one('Dimensions/Dimension[1]')
        pads[1].move_to(pattern.one('Pads'),index=0)
        self.assertEqual((2,1),(dimension['SubObject1'],dimension['SubObject2']))
        document.validate()

    def test_current_text_and_model_transforms_use_named_fields(self):
        document = parse((FIXTURES/'metadata.asc').read_bytes())
        pattern = document.one('/Library/Patterns/Pattern')
        text = pattern.one('Shapes/Shape')
        self.assertEqual(7.25,text['FontSize'])
        self.assertFalse(text['FontMono'])
        self.assertIsNone(text['Pad'])
        self.assertEqual(['First line','Second line'],[row['Text'] for row in text.select('TextLine/pt')])
        self.assertEqual((11,22,33),tuple(pattern.one('Model3D/Rotate')[axis] for axis in ('X','Y','Z')))
        self.assertEqual((13.2,-16.5,19.8),tuple(pattern.one('Model3D/Offset')[axis] for axis in ('X','Y','Z')))
        self.assertEqual('Example supplier',pattern.one('Suppliers')['Supplier'])
        text['FontSize'] = 9
        document.validate()

    def test_empty_library_and_encoding_policy(self):
        source = '(Source "DipTrace-ComLibrary" 24)(Library (Size 0)(Name "caf\xe9")(Hint "")(Categories 0)(Patterns))()'
        document = parse(source.encode('cp1252'))
        self.assertEqual('caf\xe9',document.one('/Library')['Name'])
        self.assertEqual([],document.select('/Library/Patterns/Pattern'))
        document.validate()

    def test_classification_spelling_and_mask_tuple_variants(self):
        source = (FIXTURES/'metadata.asc').read_text(encoding='cp1252')
        source = source.replace('(CategoryTypes 0','(CategoryTypes 1 (CategoryTypeType "Connector" "Jack" 2 4)')
        source = source.replace('(DisableTopPaste "N" 0 0)','(DisableTopPaste "Y" 2)')
        document = parse(source)
        pattern = document.one('/Library/Patterns/Pattern')
        self.assertEqual(('Connector','Jack',2,4),pattern.one('Pattern_CategoryTypes/CategoryType').values)
        self.assertEqual(2,pattern.one('Pads/Pad[1]')['DisableTopPaste'])
        document.validate()

    def test_empty_optional_supplier_is_the_same_as_no_supplier(self):
        source = (FIXTURES/'metadata.asc').read_text(encoding='cp1252')
        for value in ('Demo-456','Example manufacturer','Example package','Example supplier'):
            source = source.replace(value,'')
        document = parse(source)
        self.assertIsNone(document.one('/Library/Patterns/Pattern').child('Suppliers'))
        document.validate()
        invalid = source.replace('(Currency "")','(Currency "")(Prices (Unknown 5))')
        with self.assertRaises(NotImplementedError):
            parse(invalid)

    def test_inactive_pad_slots_are_not_authored_pads(self):
        source = (FIXTURES/'metadata.asc').read_text(encoding='cp1252')
        document = parse(source.replace('(Number_New 1)','(Number_New -1)'))
        pads = document.select('/Library/Patterns/Pattern/Pads/Pad')
        self.assertEqual(['2'],[pad['StringNumber'] for pad in pads])
        document.validate()

    def test_bad_counts_versions_or_unknown_meaning_are_rejected(self):
        source = (FIXTURES/'metadata.asc').read_text(encoding='cp1252')
        for before,after,error in (
                ('(Size 1)','(Size 2)',ValueError),
                ('(TextLines 2','(TextLines 1',ValueError),
                ('(SurfacePad "Y")','(SurfacePad "Perhaps")',ValueError),
                ('(Hint "Independent scalar and text examples")','(Hint "Notes")(Unknown 5)',NotImplementedError),
                ('(PadAngle 0)','(PadAngle 1)',NotImplementedError),
                ('"DipTrace-ComLibrary" 24','"DipTrace-ComLibrary" 25',UnsupportedFileError)):
            with self.subTest(before=before):
                self.assertIn(before,source)
                with self.assertRaises(error):
                    parse(source.replace(before,after))


if __name__=='__main__':
    unittest.main()
