"""Decode authored libraries, including facts beyond the older ASC dialect."""
from pathlib import Path
import unittest
from unittest.mock import patch

from lib.pattern.formats.lib.binary import PatternError
from lib.pattern.formats.lib.decode import decode
from lib.pattern.formats.lib.read import parse
from lib.pattern.formats.lib.reader import Reader


FIXTURES = Path(__file__).with_name('fixtures')


class BinaryDecodeTests(unittest.TestCase):
    def test_entry_names_and_current_text_properties(self):
        decoded = decode((FIXTURES/'metadata.lib').read_bytes())
        self.assertEqual(26, decoded.header.version)
        self.assertEqual(1, decoded.header.entry_count)
        self.assertEqual('Metadata control', decoded.root['Name'])
        pattern = decoded.root.one('Patterns/Pattern')
        self.assertEqual(('Metadata footprint','X','Example value'),
                         tuple(pattern[name] for name in ('Name','RefDes','Value')))
        shape, = [row for row in pattern.select('Shapes/Shape') if row['Type'] > 0]
        self.assertTrue(shape['Locked'])
        self.assertTrue(shape['FontMono'])
        self.assertEqual(7.25, shape['FontSize'])
        self.assertEqual(1.5, shape['FontScale'])
        self.assertEqual(2, shape['PadId'])
        self.assertEqual(['First line','Second line'],
                         [row.values[0] for row in shape.select('TextLine/pt')])

    def test_distinct_3d_transforms_have_their_named_meaning(self):
        model = decode((FIXTURES/'metadata.lib').read_bytes()).root.one('Patterns/Pattern/Model3D')
        for name,values in (('Rotate',(11,22,33)),('Offset',(13.2,-16.5,19.8)),
                            ('Zoom',(1.1,1.2,1.3))):
            with self.subTest(name=name):
                self.assertEqual(values,tuple(model.one(name)[axis] for axis in ('X','Y','Z')))
        self.assertEqual('example.step',model['Model3DFile'])
        self.assertEqual('example.step',model['Model3DFile_Variable'])
        self.assertTrue(model['Mirror'])
        self.assertTrue(model['NoSearch'])
        self.assertTrue(model['KeepPins'])
        self.assertEqual(0x123456,model['AutoColor'])
        self.assertEqual((3.3,-6.6,9.9),tuple(model[name] for name in ('IPC_XOff','IPC_YOff','AutoHeight')))

    def test_interleaved_groups_and_dimension_attachments(self):
        pattern = decode((FIXTURES/'geometry.lib').read_bytes()).root.one('Patterns/Pattern')
        pads = [pad for pad in pattern.select('Pads/Pad') if pad['Number_New'] > 0]
        self.assertEqual(['1','2'],[pad['StringNumber'] for pad in pads])
        self.assertEqual([0,-1],[pad['Group'] for pad in pads])
        holes = pattern.select('Holes/Hole')
        self.assertEqual(3,len(holes))
        self.assertEqual((True,False,4.5,0.75,6,3,0),holes[1].values)
        dimensions = pattern.select('Dimensions/Dimension')
        self.assertEqual(2,len(dimensions))
        first,second = dimensions
        self.assertEqual((0,1,0,2,-1),tuple(first[name] for name in
                         ('Connected1','SubObject1','Connected2','SubObject2','Group')))
        self.assertEqual((1,1,2,1,0),tuple(second[name] for name in
                         ('Connected1','SubObject1','Connected2','SubObject2','Group')))

    def test_truncated_or_trailing_data_is_rejected(self):
        data = (FIXTURES/'metadata.lib').read_bytes()
        for end in (0,12,len(data)//2,len(data)-1):
            with self.subTest(end=end),self.assertRaises(ValueError):
                decode(data[:end])
        with self.assertRaisesRegex(PatternError,'unconsumed library data'):
            decode(data+b'extra')


class BinaryModelTests(unittest.TestCase):
    def test_inactive_pad_slots_preserve_remaining_pad_identities(self):
        data = bytearray((FIXTURES/'geometry.lib').read_bytes())
        with patch.object(Reader,'retain_source',True):
            decoded = decode(data)
        field = decoded.root.one('Patterns/Pattern/Pads/Pad[2]/Number_New')
        offset = field.source.start
        data[offset:offset+3] = (999999).to_bytes(3,'big')
        document = parse(data)
        pads = document.select('/Library/Patterns/Pattern/Pads/Pad')
        self.assertEqual(['2'],[pad['StringNumber'] for pad in pads])
        self.assertTrue(document.references.issues)
        document.validate()

    def test_inactive_measurement_slots_do_not_create_live_attachments(self):
        data = bytearray((FIXTURES/'geometry.lib').read_bytes())
        with patch.object(Reader,'retain_source',True):
            decoded = decode(data)
        enabled = decoded.root.one('Patterns/Pattern/Dimensions/Dimension[1]/Enabled')
        offset = enabled.source.start
        self.assertEqual(1,data[offset])
        data[offset] = 0
        document = parse(data)
        self.assertEqual(1,len(document.select('/Library/Patterns/Pattern/Dimensions/Dimension')))
        document.validate()

    def test_arrays_become_owned_objects_with_coordinated_identity_links(self):
        document = parse((FIXTURES/'geometry.lib').read_bytes())
        pattern = document.one('/Library/Patterns/Pattern')
        pads = pattern.select('Pads/Pad')
        shape = pattern.one('Shapes/Shape')
        self.assertEqual((2,1,1),(len(pads),len(pattern.select('Shapes/Shape')),len(pattern.select('Holes/Hole'))))
        self.assertIs(pads[1],shape['Pad'])
        self.assertIs(pattern.one('Pattern_Groups/pt'),pads[0]['Group'])
        dimension = pattern.one('Dimensions/Dimension[1]')
        self.assertEqual((1,2),(dimension['SubObject1'],dimension['SubObject2']))
        pads[1].move_to(pattern.one('Pads'),index=0)
        self.assertEqual((2,1),(dimension['SubObject1'],dimension['SubObject2']))
        self.assertEqual(1,shape['PadId'])
        document.validate()

    def test_binary_font_and_supplier_data_are_editable_model_facts(self):
        document = parse((FIXTURES/'metadata.lib').read_bytes())
        pattern = document.one('/Library/Patterns/Pattern')
        text = pattern.one('Shapes/Shape')
        self.assertEqual((True,7.25),(text['FontMono'],text['FontSize']))
        text['FontSize'] = 8.5
        supplier = pattern.one('Suppliers')
        self.assertEqual('Demo-456',supplier['PartNumber'])
        supplier['PartNumber'] = 'Revised-789'
        clone = document.clone()
        self.assertEqual(8.5,clone.one('/Library/Patterns/Pattern/Shapes/Shape')['FontSize'])
        self.assertEqual('Revised-789',clone.one('/Library/Patterns/Pattern/Suppliers')['PartNumber'])
        clone.validate()


if __name__ == '__main__':
    unittest.main()
