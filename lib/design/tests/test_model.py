"""Behavioral tests for our document API and ASC adapter (self-contained fixtures)."""
from pathlib import Path
import sys
import unittest
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from lib.design import Document, Element, Value, parse_asc, IncompleteDocumentError


class DocumentTests(unittest.TestCase):
    def test_reported_paths_resolve_every_element_including_the_root(self):
        for node in self.doc.root.walk(include_self=True):
            self.assertIs(self.doc.one(node.path), node)
            self.assertIs(node.one(node.path), node)
        part = self.doc.one('//Part')
        part.move_to(self.doc.one('/Schematic/Other'))
        for node in part.walk(include_self=True):
            self.assertIs(self.doc.one(node.path), node)

    def test_boolean_queries_distinguish_boolean_and_numeric_data(self):
        document = Document()
        for value in (True, False, 1, 0):
            document.root.add('Item').add('Flag', value)
        self.assertEqual([node.scalar('Flag') for node in document.select('/Item[Flag=true]')], [True])
        self.assertEqual([node.scalar('Flag') for node in document.select('/Item[Flag=FALSE]')], [False])
        self.assertEqual([node.scalar('Flag') for node in document.select('/Item[Flag=1]')], [1])
        self.assertEqual(len(document.select('/Item[Flag=0]')), 1)
        for literal in ('NaN', 'Infinity', 'sNaN'):
            with self.subTest(literal=literal), self.assertRaisesRegex(ValueError, 'finite'):
                document.select('/Item[Flag='+literal+']')

    def test_quoted_query_text_can_contain_quotes_separators_and_backslashes(self):
        document = Document()
        value = 'A "quoted" / [name] with \'apostrophes\' and C:\\Library\\'
        item = document.root.add('Item', value)
        item.add('Name', value)
        for quote in ('"', "'"):
            literal = quote+value.replace(quote, quote*2)+quote
            self.assertEqual(document.select('/Item[Name='+literal+']'), [item])
            self.assertEqual(document.select('/Item[@0='+literal+']'), [item])

    def setUp(self):
        self.text = '(Source "DipTrace-Schematic" 46)\r\n(Schematic\r\n  (Components\r\n    (Part "CAP" "C1"\r\n      (Value "100n")\r\n      (X -0.0000)\r\n      (Tag A)\r\n      (Tag B)\r\n    )\r\n  )\r\n  (Scale 100.00%)\r\n  (Other\r\n  )\r\n)\r\n'
        self.doc = parse_asc(self.text)

    def test_exact_preservation_and_scalar_patch(self):
        self.assertEqual(self.doc.to_asc(), self.text)
        part = self.doc.one('/Schematic/Components/Part[@1="C1"]')
        part.set_field("Value", "220n")
        self.assertEqual(self.doc.to_asc(), self.text.replace('"100n"', '"220n"'))
        self.assertEqual(part.scalar("X"), Decimal("-0.0000"))
        self.assertEqual(self.doc.one('//Scale').arguments[0].unit, "%")

    def test_duplicate_fields_query_and_clone(self):
        part = self.doc.one('//Part[Value="100n"]')
        self.assertEqual([n.values for n in part.children("Tag")], [("A",), ("B",)])
        self.assertEqual(part.scalar("Tag", occurrence=1), "B")
        copied = part.clone()
        copied.set_argument(1, "C2")
        copied.set_field("Value", "1u")
        part.parent.append(copied)
        self.assertEqual(len(self.doc.select('//Part')), 2)
        self.assertNotEqual(copied.uid, part.uid)
        reread = parse_asc(self.doc.to_asc())
        self.assertEqual(reread.one('//Part[@1="C2"]').scalar("Value"), "1u")
        self.assertEqual(part.scalar("Value"), "100n")

    def test_moves_are_atomic_and_preserve_identity(self):
        part = self.doc.one('//Part')
        before, parent, uid = self.doc.to_asc(), part.parent, part.uid
        with self.assertRaises(IndexError):
            part.move_to(self.doc.one('/Schematic/Other'), 2)
        self.assertIs(part.parent, parent)
        self.assertEqual(self.doc.to_asc(), before)
        with self.assertRaises(ValueError):
            parent.move_to(part)
        part.move_to(self.doc.one('/Schematic/Other'))
        self.assertEqual(part.uid, uid)
        self.assertEqual(self.doc.one('/Schematic/Other/Part').scalar("Value"), "100n")
        self.assertEqual(len(parse_asc(self.doc.to_asc()).select('/Schematic/Other/Part')), 1)
        self.doc.rebuild_index()

    def test_new_model_has_no_binary_dependency(self):
        doc = Document()
        schematic = doc.root.add("Schematic")
        part = schematic.add("Components").add("Part", "RES", "R1")
        part.set_field("Value", "10k")
        part.set_field("X", Decimal("12.3456"))
        text = doc.to_asc()
        self.assertIn('(X 12.3456)', text)
        self.assertEqual(parse_asc(text).one('//Part').values, ("RES", "R1"))
        self.assertIn('(Value "10k")', text)

    def test_strings_do_not_interpret_path_backslashes(self):
        text = '(Path "C:\\Library\\")\n(Label "mu µ and Ω")\n'
        self.assertEqual(parse_asc(text).to_asc(), text)
        doc = parse_asc(text)
        doc.one('/Label').set_argument(0, "changed")
        self.assertEqual(doc.to_asc(), text.replace('mu µ and Ω', 'changed'))

    def test_invalid_syntax_is_rejected(self):
        for text in ['(Part "unfinished)', '(Part', ')', '(A 1))', 'outside', '(A "x") "outside"']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_asc(text)

    def test_no_silent_export_of_incomplete_load(self):
        self.doc.complete = False
        self.doc.diagnostics.append("unmapped shape data")
        with self.assertRaises(IncompleteDocumentError):
            self.doc.to_asc()
        self.assertEqual(self.doc.to_asc(allow_partial=True), self.text)

    def test_value_changes_cannot_bypass_dirty_tracking(self):
        from dataclasses import FrozenInstanceError
        with self.assertRaises(FrozenInstanceError):
            self.doc.one('//Value').arguments[0].value = "changed"
        doc = self.doc.clone()
        doc.one('//Value').set_argument(0, "changed")
        self.assertEqual(self.doc.to_asc(), self.text)
        self.assertIn('"changed"', doc.to_asc())

    def test_moving_edited_subtree_keeps_multiline_string_content(self):
        text = '(A\n  (B\n    (Label "one\n  two")\n    (X 1)\n  )\n)\n(C\n  (D\n  )\n)\n'
        doc = parse_asc(text)
        b = doc.one('/A/B')
        b.set_field('X', 2)
        b.move_to(doc.one('/C/D'))
        rendered = doc.to_asc()
        reread = parse_asc(rendered)
        self.assertEqual(reread.one('/C/D/B/Label').values, ('one\n  two',))
        self.assertEqual(reread.one('/C/D/B/X').values, (2,))
        self.assertIn('\n      (X 2)\n    )', rendered)

    def test_setting_same_numeric_value_preserves_spelling(self):
        node = self.doc.one('//X')
        node.set_argument(0, Decimal('0'))
        self.assertEqual(self.doc.to_asc(), self.text)

    def test_explicit_values_can_replace_spelling_and_provenance(self):
        from lib.design import SourceSpan
        node = self.doc.one('//X')
        first = Value(Decimal('0'), 'number', lexeme='0.0', source=SourceSpan('example', 1, 2))
        node.set_argument(0, first)
        self.assertIs(node.arguments[0], first)
        self.assertIn('(X 0.0)', self.doc.to_asc())
        second = Value(Decimal('0'), 'number', lexeme='0.00', source=SourceSpan('example', 5, 6))
        node.set_values(second)
        self.assertIs(node.arguments[0], second)
        self.assertIn('(X 0.00)', self.doc.to_asc())

    def test_new_formats_can_share_the_document_model(self):
        from lib.design import register_reader, register_writer, read, write
        from unittest.mock import patch
        import lib.design as design
        # Isolate registrations so repeated test runs do not mutate the API.
        with patch.dict(design._READERS), patch.dict(design._WRITERS):
            register_reader('example', lambda path, **options: parse_asc('(Label "shared model")\n'))
            captured = []
            register_writer('example', lambda doc, path, **options: captured.append(doc.one('/Label').values))
            doc = read('input.example')
            doc.one('/Label').set_argument(0, 'edited')
            write(doc, 'output.example')
            self.assertEqual(captured, [('edited',)])
            with self.assertRaises(ValueError):
                register_reader('example', lambda path: Document())


if __name__ == '__main__':
    unittest.main()
