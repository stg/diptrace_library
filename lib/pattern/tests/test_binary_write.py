"""Standalone output follows current data, references and destination gates."""
from pathlib import Path
import unittest
from unittest.mock import patch

from lib.common.conversion import ConversionReport
from lib.common.errors import UnsupportedFileError
from lib.pattern.formats.lib.binary import Cursor
from lib.pattern.formats.lib.decode import decode
from lib.pattern.formats.lib.read import parse
from lib.pattern.formats.lib.write import encode
from lib.pattern.formats.libxml.read import parse as read_xml
from lib.pattern.model import new_library,new_pattern

FIXTURES=Path(__file__).with_name('fixtures')


def facts(document):
    return ([(node.path,node.kind,node.values) for node in document.root.walk(include_self=True)],
            sorted((r.source.path,r.target.path,r.role) for r in document.references))


class BinaryWriteTests(unittest.TestCase):
    def test_current_geometry_and_reordered_links_survive(self):
        document=parse((FIXTURES/'geometry.lib').read_bytes())
        pattern=document.one('/Library/Patterns/Pattern')
        pads=pattern.select('Pads/Pad')
        pads[0]['StringNumber']='A19'
        pads[1].move_to(pattern.one('Pads'),index=0)
        pattern.one('Shapes/Shape')['Width']=.6
        before=facts(document)
        output=parse(encode(document))
        self.assertEqual(before,facts(document))
        pattern=output.one('/Library/Patterns/Pattern')
        pads=pattern.select('Pads/Pad')
        self.assertEqual(['2','A19'],[p['StringNumber'] for p in pads])
        self.assertIs(pads[0],pattern.one('Shapes/Shape')['Pad'])
        dimension=pattern.one('Dimensions/Dimension[1]')
        self.assertEqual((2,1),(dimension['SubObject1'],dimension['SubObject2']))
        self.assertIs(pattern.one('Pattern_Groups/pt'),pads[1]['Group'])
        self.assertEqual(.6,pattern.one('Shapes/Shape')['Width'])
        output.validate()

    def test_empty_and_multiple_entries_with_declared_catalogue_keys(self):
        document=new_library('Examples',hint='Independent Unicode \u03bc examples')
        self.assertEqual([],parse(encode(document)).select('/Library/Patterns/Pattern'))
        library=document.one('/Library')
        category=library.one('Categories').add('Category','Assembly',7)
        category.add('Type','Header',12).add('Subtype','Through',31)
        for name in ('First','Second'):
            pattern=new_pattern(name)
            pattern['RefDes']='X'
            pattern['Pattern_CategoryName']='Assembly'
            pattern['Pattern_CategoryIndex']=7
            pattern.one('Pattern_CategoryTypes').add('CategoryType','Header','Through',12,31)
            library.one('Patterns').append(pattern)
        for version in (24,25,26):
            with self.subTest(version=version):
                output=parse(encode(document,version=version))
                self.assertEqual(['First','Second'],[p['Name'] for p in output.select('/Library/Patterns/Pattern')])
                row=output.one('/Library/Categories/Category/Type/Subtype')
                self.assertEqual(('Through',31),row.values)
                self.assertEqual(library['Hint'],output.one('/Library')['Hint'])
                self.assertEqual(('Header','Through',12,31),
                    output.one('/Library/Patterns/Pattern[1]/Pattern_CategoryTypes/CategoryType').values)

    def test_new_font_properties_and_model_vectors_are_written(self):
        document=parse((FIXTURES/'metadata.lib').read_bytes())
        output=parse(encode(document,version=26))
        shape=output.one('/Library/Patterns/Pattern/Shapes/Shape')
        self.assertEqual((7.25,True),(shape['FontSize'],shape['FontMono']))
        self.assertEqual(['First line','Second line'],[r['Text'] for r in shape.select('TextLine/pt')])
        model=output.one('/Library/Patterns/Pattern/Model3D')
        self.assertEqual((11,22,33),tuple(model.one('Rotate')[k] for k in ('X','Y','Z')))
        self.assertEqual((13.2,-16.5,19.8),tuple(model.one('Offset')[k] for k in ('X','Y','Z')))
        self.assertEqual('Demo-456',output.one('/Library/Patterns/Pattern/Suppliers')['PartNumber'])

    def test_older_destination_projects_a_copy_and_reports_specific_loss(self):
        document=parse((FIXTURES/'metadata.lib').read_bytes())
        before=facts(document)
        for version in (24,25):
            with self.subTest(version=version):
                report=ConversionReport()
                output=parse(encode(document,version=version,report=report))
                shape=output.one('/Library/Patterns/Pattern/Shapes/Shape')
                self.assertEqual((7,False),(shape['FontSize'],shape['FontMono']))
                expected={'fractional-font-size','monospaced-font'}
                if version==24:
                    expected.add('drawing-pad-reference')
                    self.assertIsNone(shape['Pad'])
                else:
                    self.assertIsNotNone(shape['Pad'])
                self.assertEqual(expected,{notice.rule for notice in report.warnings})
                self.assertEqual(before,facts(document))

    def test_serialization_token_is_fresh_output_bookkeeping(self):
        document=parse((FIXTURES/'metadata.lib').read_bytes())
        with patch('lib.pattern.formats.lib.writer.secrets.randbits',side_effect=(17,29)):
            first,second=encode(document),encode(document)
        cursor=Cursor(first)
        offset=cursor.pos
        self.assertEqual((17,29),tuple(int.from_bytes(data[offset:offset+4],'little') for data in (first,second)))
        self.assertEqual(first[:offset]+first[offset+4:],second[:offset]+second[offset+4:])
        self.assertNotIn('UID32',document.one('/Library').schema.fields)

    def test_writer_builds_boundary_rows_without_retaining_input_slots(self):
        document=parse((FIXTURES/'geometry.lib').read_bytes())
        current=document.one('/Library/Patterns/Pattern')
        raw=decode(encode(document)).root.one('Patterns/Pattern')
        pads=raw.select('Pads/Pad')
        self.assertEqual([-1,1,2,-1],[p['Number_New'] for p in pads])
        self.assertEqual(len(current.select('Shapes/Shape'))+2,len(raw.select('Shapes/Shape')))
        self.assertEqual(len(current.select('Holes/Hole'))+2,len(raw.select('Holes/Hole')))
        self.assertEqual(2,len(current.select('Pads/Pad')))

    def test_unmapped_data_fails_and_unavailable_links_project_with_warnings(self):
        document=parse((FIXTURES/'geometry.lib').read_bytes())
        document.one('/Library/Patterns/Pattern').add('UnknownData',42)
        report=ConversionReport()
        with self.assertRaises(NotImplementedError):
            encode(document,report=report)
        self.assertEqual(1,len(report.errors))
        source=(FIXTURES/'geometry_input.libxml').read_text().replace('Group="8"','Group="99"')
        document=read_xml(source)
        report = ConversionReport()
        result = parse(encode(document, report=report))
        self.assertEqual([], result.references.issues)
        self.assertIn('unresolved-local-reference', {notice.rule for notice in report.warnings})
        self.assertTrue(document.references.issues)

    def test_unsupported_output_revision_has_family_metadata(self):
        report=ConversionReport()
        with self.assertRaises(UnsupportedFileError) as caught:
            encode(new_library(),version=23,report=report)
        error=caught.exception
        self.assertEqual(('pattern','lib',23,'version'),(error.family,error.format,error.version,error.reason))
        self.assertEqual(1,len(report.errors))


if __name__=='__main__':
    unittest.main()
