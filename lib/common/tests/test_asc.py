"""The shared ASC codec parses syntax without selecting a document family."""
from decimal import Decimal
import unittest

from lib.common import asc
from lib.common.model import Document


class AscTests(unittest.TestCase):
    def test_no_source_mode_preserves_tokens_and_semantics_without_spans(self):
        text = '(Component "Example" 003 (X -0.0000) (X -0.0000) (Name Inner!1))'
        detailed = asc.loads(text)
        lean = asc.loads_bytes(text.encode(), retain_source=False)
        self.assertEqual(asc.dumps(lean, preserve=False), asc.dumps(detailed, preserve=False))
        self.assertIsNone(lean._source_text)
        self.assertIsNone(lean._source_bytes)
        for node in lean.root.walk(include_self=True):
            self.assertIsNone(node.source)
            self.assertIsNone(node._syntax)
            self.assertTrue(all(value.source is None for value in node.arguments))
        self.assertEqual(lean.one('/Component').arguments[1].lexeme, '003')
        self.assertIs(lean.one('//X[1]').arguments[0], lean.one('//X[2]').arguments[0])
        lean.one('//X[1]').set_argument(0, 5)
        self.assertEqual(lean.one('//X[2]').values, (Decimal('-0.0000'),))

    def test_no_source_mode_keeps_malformed_input_rejection(self):
        for text in ('(Name "unterminated)', '(Name 1', '(Name 1))', 'outside', '(1Name x)'):
            for retain in (False, True):
                with self.subTest(text=text, retain=retain), self.assertRaises(ValueError):
                    asc.loads(text, retain_source=retain)

    def test_pcb_source_has_no_schematic_dependencies(self):
        text = '(Source "DipTrace-PCBN" 53)\r\n(Board (Points (pt 1.25 -2.5 "N")))\r\n'
        document = asc.loads(text)
        self.assertIs(type(document), Document)
        self.assertEqual(document.one('/Source').values, ('DipTrace-PCBN', 53))
        point = document.one('/Board/Points/pt')
        self.assertEqual(point.values, (Decimal('1.25'), Decimal('-2.5'), 'N'))
        self.assertEqual(asc.dumps(document), text)
        point.set_argument(0, 3)
        output = asc.dumps(document)
        self.assertEqual(output, text.replace('1.25', '3'))
        self.assertEqual(asc.loads(output).one('/Board/Points/pt').values[0], 3)

    def test_a_family_can_supply_its_document_class(self):
        class FamilyDocument(Document):
            pass

        document = asc.loads_bytes(b'(Source "Example" 1)', document_factory=FamilyDocument)
        self.assertIs(type(document), FamilyDocument)
        self.assertEqual(document.metadata['source_format'], 'asc')

    def test_render_without_source_syntax(self):
        document = Document()
        document.root.add('Source', 'DipTrace-PCBN', 53)
        document.root.add('Board').add('Enabled', True)
        output = asc.dumps(document, preserve=False)
        self.assertEqual(asc.loads(output).one('/Board/Enabled').values, ('Y',))

    def test_bare_names_can_contain_punctuation(self):
        text = '(Layers (Name Inner!1) (Name Top!!Signal!))'
        document = asc.loads(text)
        self.assertEqual([node.values[0] for node in document.select('/Layers/Name')],
                         ['Inner!1', 'Top!!Signal!'])
        self.assertEqual(asc.loads(asc.dumps(document, preserve=False)).one('/Layers/Name[1]').values,
                         ('Inner!1',))


if __name__ == '__main__':
    unittest.main()
