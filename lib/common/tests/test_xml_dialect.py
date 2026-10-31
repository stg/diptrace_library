"""Typed XML text can depend on ownership when public tag names overlap."""
import unittest

from lib.common.xml import XmlDialect, loads, dumps


class XmlDialectTests(unittest.TestCase):
    dialect = XmlDialect(boolean_text=frozenset({('Assembly', 'Silk'), 'Visible'}),
                         number_text=frozenset({('LineWidth', 'Silk')}))

    def test_scoped_boolean_and_numeric_text_with_the_same_name_round_trip(self):
        text = '<Source><Assembly><Silk>Y</Silk></Assembly><LineWidth><Silk>0.25</Silk></LineWidth><Visible>N</Visible></Source>'
        document = loads(text, dialect=self.dialect)
        self.assertIs(document.one('/Source/Assembly/Silk').values[0], True)
        self.assertEqual(document.one('/Source/LineWidth/Silk').values[0], 0.25)
        self.assertIs(document.one('/Source/Visible').values[0], False)
        restored = loads(dumps(document, dialect=self.dialect), dialect=self.dialect)
        self.assertEqual(restored.one('/Source/Assembly/Silk').values, (True,))
        self.assertEqual(restored.one('/Source/LineWidth/Silk').values,
                         document.one('/Source/LineWidth/Silk').values)

    def test_scoped_boolean_lexical_validation_does_not_type_unrelated_text(self):
        with self.assertRaisesRegex(ValueError, 'invalid XML boolean'):
            loads('<Source><Assembly><Silk>Yes</Silk></Assembly></Source>', dialect=self.dialect)
        other = loads('<Source><Other><Silk>literal</Silk></Other></Source>', dialect=self.dialect)
        self.assertEqual(other.one('/Source/Other/Silk').values, ('literal',))

    def test_attribute_types_can_be_scoped_without_changing_other_owners(self):
        dialect = XmlDialect(boolean_attributes=frozenset({('LayerPanel', 'TopPaste')}),
                             number_attributes=frozenset({('Size', 'Value')}))
        document = loads('<Source><LayerPanel TopPaste="Y"/><MaskPaste TopPaste="Segments"/>'
                         '<Size Value="2"/><Label Value="text"/></Source>', dialect=dialect)
        self.assertIs(document.one('/Source/LayerPanel/TopPaste').values[0], True)
        self.assertEqual(document.one('/Source/MaskPaste/TopPaste').values, ('Segments',))
        self.assertEqual(document.one('/Source/Size/Value').values, (2,))
        self.assertEqual(document.one('/Source/Label/Value').values, ('text',))
        restored = loads(dumps(document, dialect=dialect), dialect=dialect)
        self.assertIs(restored.one('/Source/LayerPanel/TopPaste').values[0], True)
        document.one('/Source/LayerPanel/TopPaste').set_values('Y')
        with self.assertRaisesRegex(ValueError, 'expected an XML boolean'):
            dumps(document, dialect=dialect)

    def test_scoped_numeric_attribute_validation_applies_to_output(self):
        dialect = XmlDialect(number_attributes=frozenset({('Item', 'Name')}))
        document = loads('<Source><Item Name="17"><Name>Display</Name></Item></Source>', dialect=dialect)
        attribute, element = document.one('/Source/Item').children('Name')
        self.assertEqual((attribute.values, element.values), ((17,), ('Display',)))
        attribute.set_values('17')
        with self.assertRaisesRegex(ValueError, 'expected an XML number'):
            dumps(document, dialect=dialect)


if __name__ == '__main__':
    unittest.main()
