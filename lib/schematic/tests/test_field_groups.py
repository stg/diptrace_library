"""Public tuple groups have searchable, editable named storage."""
import unittest

from lib import ConversionReport, Element, parse, serialize
from lib.schematic.model.refs import bind_schematic_references
from lib.schematic.tests.test_named_fields import design


PART = '/Schematic/Components/Part'


class FieldGroupTests(unittest.TestCase):
    def test_marking_members_are_real_named_fields_with_a_tuple_view(self):
        doc = design()
        part = doc.one(PART)
        setting = part.one('ShowRefDes')
        self.assertTrue(all(isinstance(item, Element) for item in setting.items))
        setting['X'] = 12.75
        self.assertEqual(part['ShowRefDes'][5], 12.75)
        self.assertEqual(part.scalar('ShowRefDes'), part['ShowRefDes'])
        self.assertEqual(setting.schema.field('Angle').unit, 'radians')
        self.assertEqual(part.schema.field('ShowRefDes').members[5].name, 'X')
        self.assertIs(doc.one('//ShowRefDes[X=12.75]'), setting)

    def test_tuple_and_member_validation_reject_bad_edits_before_changes(self):
        part = design().one(PART)
        before = part['ShowRefDes']
        for edit in (lambda: part.one('ShowRefDes').set('X', 'invalid'),
                     lambda: part.set('ShowRefDes', (True, *before[1:])),
                     lambda: part.set('ShowRefDes', before[:-1])):
            with self.assertRaises((TypeError, ValueError)):
                edit()
            self.assertEqual(part['ShowRefDes'], before)

    def test_local_and_global_suffix_changes_refresh_bound_text_immediately(self):
        doc = design()
        part = doc.one(PART)
        text = next(shape for shape in part.select('Shapes/Shape') if shape['FontType'] == 2)
        part['AllowParts'] = True
        part['PartDescriptor'] = 'B'
        self.assertEqual(text.one('TextLine/pt').values, ('R1.B',))
        part.one('ShowRefDes')['ShowPart'] = 2
        self.assertEqual(text.one('TextLine/pt').values, ('R1',))
        part.one('ShowRefDes')['ShowPart'] = 0
        self.assertEqual(text.one('TextLine/pt').values, ('R1.B',))
        doc.one('/Schematic/ShowRefDes_Global')['ShowPart'] = 2
        self.assertEqual(text.one('TextLine/pt').values, ('R1',))

    def test_user_field_type_and_label_members_cross_every_format_pair(self):
        source = design()
        field = source.one(PART+'/UserFields').add('UserField', 'Link', 'example.invalid', 1,
                                                  1, 8, 0, 0, 0, 0, 0)
        bind_schematic_references(source)
        self.assertEqual(field['Type'], 1)
        for incoming in ('dch', 'asc', 'dchxml'):
            doc = parse(serialize(source, format=incoming, report=ConversionReport()),
                        format=incoming, report=ConversionReport())
            setting = doc.one(PART+'/ShowRefDes')
            setting['Align'] = 8
            setting['X'] = 12.75
            setting['Y'] = -3.75
            field = doc.one(PART+'/UserFields/UserField')
            field['Value'] = 'updated.invalid'
            self.assertEqual(field['Type'], 1)
            for outgoing in ('dch', 'asc', 'dchxml'):
                with self.subTest(incoming=incoming, outgoing=outgoing):
                    result = parse(serialize(doc, format=outgoing, report=ConversionReport()),
                                   format=outgoing, report=ConversionReport())
                    restored = result.one(PART+'/ShowRefDes')
                    self.assertEqual((restored['X'], restored['Y']), (12.75, -3.75))
                    self.assertEqual(result.one(PART+'/UserFields/UserField')['Value'], 'updated.invalid')
                    self.assertEqual(result.one(PART+'/UserFields/UserField')['Type'], 1)
