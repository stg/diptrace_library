"""A document family supplies vocabulary without replacing the XML parser."""
from decimal import Decimal, localcontext
import unittest

from lib.common import xml
from lib.common.model import Document


PCB = xml.XmlDialect(format='dipxml', source_type='DipTrace-PCB',
    number_attributes=frozenset(('X', 'Y')),
    boolean_attributes=frozenset(('Locked',)),
    number_text=frozenset((('Origin', 'X'),)),
    boolean_text=frozenset(('Visible',)))


class XmlTests(unittest.TestCase):
    def test_rendering_and_style_keys_do_not_add_annotation_maps(self):
        from lib.common.xml_catalog import record_key
        document = Document()
        source = document.root.add('Source')
        xml.set_attribute(source, 'Type', 'DipTrace-PCB')
        item = source.add('Item', 'content')
        snapshot = [(node, node._annotations) for node in document.root.walk(include_self=True)]
        key = record_key(source)
        self.assertEqual(key[3], (('Item', (('string', 'content', ''),), (), ()),))
        self.assertIn('<Item>content</Item>', xml.dumps(document, dialect=PCB))
        for node, notes in snapshot:
            self.assertIs(node._annotations, notes)
        self.assertIsNone(item._annotations)

    def test_invalid_new_attribute_does_not_leave_an_empty_field(self):
        document = xml.loads('<Source Type="DipTrace-PCB"/>', dialect=PCB)
        source = document.one('Source')
        with self.assertRaises(ValueError):
            xml.set_attribute(source, 'X', float('inf'))
        self.assertIsNone(source.child('X'))

    def test_equivalent_numeric_spellings_have_stable_output_without_rounding(self):
        for literal, expected in (('1.840', '1.84'), ('-0.0000', '0'),
                                  ('123000.0', '123000'), ('1E+3', '1000'),
                                  ('123456.78900', '123456.789')):
            with self.subTest(literal=literal), localcontext() as context:
                context.prec = 2
                document = xml.loads(f'<Source Type="DipTrace-PCB"><Value X="{literal}"/></Source>', dialect=PCB)
                output = xml.dumps(document, dialect=PCB, canonical_numbers=True)
                self.assertIn(f'X="{expected}"', output)
                self.assertEqual(xml.dumps(xml.loads(output, dialect=PCB), dialect=PCB, canonical_numbers=True), output)

    def test_typed_data_survives_syntax_round_trip(self):
        document = xml.loads('<Source Type="DipTrace-PCB"><Board><Component '
            'X="1.25" Y="-2" Locked="Y"><RefDes>R01</RefDes></Component>'
            '<Origin><X>2.5</X><Visible>N</Visible></Origin></Board></Source>', dialect=PCB)
        component = document.one('/Source/Board/Component')
        self.assertEqual(component.scalar('X'), Decimal('1.25'))
        self.assertIs(component.scalar('Locked'), True)
        self.assertEqual(component.scalar('RefDes'), 'R01')
        component.one('X').set_values(3)
        reparsed = xml.loads(xml.dumps(document, dialect=PCB), dialect=PCB)
        self.assertEqual(reparsed.one('/Source/Board/Component').scalar('X'), 3)
        self.assertEqual(reparsed.one('/Source/Board/Origin').scalar('X'), Decimal('2.5'))
        self.assertIs(reparsed.one('/Source/Board/Origin').scalar('Visible'), False)
        self.assertEqual(document.metadata['source_format'], 'dipxml')

    def test_dialects_do_not_change_each_others_vocabulary(self):
        data = '<Source Type="DipTrace-PCB"><Value X="1" Locked="Y"/></Source>'
        generic = xml.loads(data)
        typed = xml.loads(data, dialect=PCB)
        self.assertEqual(generic.one('/Source/Value').scalar('X'), '1')
        self.assertEqual(typed.one('/Source/Value').scalar('X'), 1)
        self.assertEqual(generic.one('/Source/Value').scalar('Locked'), 'Y')
        with self.assertRaisesRegex(ValueError, 'DipTrace-PCB'):
            xml.loads('<Source Type="Other"/>', dialect=PCB)

    def test_family_document_factory_and_unknown_fields(self):
        class FamilyDocument(Document):
            pass

        document = xml.loads('<Source Type="DipTrace-PCB"><Vendor Custom="001">007</Vendor></Source>',
                             dialect=PCB, document_factory=FamilyDocument)
        self.assertIs(type(document), FamilyDocument)
        self.assertEqual(document.one('/Source/Vendor').scalar('Custom'), '001')
        self.assertEqual(document.one('/Source/Vendor').values, ('007',))
        self.assertIn('Custom="001">007</Vendor>', xml.dumps(document, dialect=PCB))

    def test_document_type_declarations_and_invalid_typed_values_fail(self):
        for data in ('<!DOCTYPE Source [<!ENTITY data "external">]><Source/>',
                     '<Source Type="DipTrace-PCB"><Item Locked="yes"/></Source>',
                     '<Source Type="DipTrace-PCB"><Item X="nan"/></Source>'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                xml.loads(data, dialect=PCB)


if __name__ == '__main__':
    unittest.main()
