"""Generic library attachment keeps named editing typed and atomic."""
import unittest

from lib.common.library_document import LibraryDocument
from lib.common.model import Element
from lib.common.schema import Child, Field, Record
from lib.common.schema_catalogue import declared_child

ROW = Record('ExampleRow', {
    'Name': Field('Name', 'text', required=True),
    'X': Field('X', 'number', required=True),
    'Index': Field('Index', 'integer', getter=lambda node: node._ordinal(),
                   ordinal_dependencies=lambda node: (node,)),
}, ('Name', 'X'))
ROWS = Record('ExampleRows', {}, children={'Row': Child('Row', ROW.name, maximum=None)})
ROOT = Record('ExampleDocument', {}, children={'Rows': Child('Rows', ROWS.name)})
SCHEMA = {record.name: record for record in (ROOT, ROWS, ROW)}


class ExampleDocument(LibraryDocument):
    _representations = (*LibraryDocument._representations, 'example')
    _named_representations = ('example',)

    def __init__(self, root=None, *, representation='example'):
        super().__init__(root if root is not None else Element('').bind_schema(ROOT), representation=representation)

    def _record_definition(self, node):
        return declared_child(node.parent.schema, node.kind, SCHEMA) if node.parent else ROOT


class LibraryDocumentTests(unittest.TestCase):
    def test_new_rows_immediately_support_named_editing_and_clone(self):
        document = ExampleDocument()
        rows = document.root.add('Rows')
        first = rows.add('Row', 'First', 1)
        second = rows.add('Row', 'Second', 2)
        first['X'] = 3
        self.assertEqual(('First', 3, 0), (first['Name'], first['X'], first['Index']))
        second.move_to(rows, index=0)
        self.assertEqual((1, 0), (first['Index'], second['Index']))
        clone = document.clone()
        self.assertEqual('Second', clone.one('/Rows/Row[1]')['Name'])
        document.validate()
        clone.validate()

    def test_invalid_attachment_restores_both_proposal_and_document(self):
        document = ExampleDocument()
        rows = document.root.add('Rows')
        rows.add('Row', 'Existing', 1)
        invalid = Element('Row', 123, 2)
        with self.assertRaises(TypeError):
            rows.append(invalid)
        self.assertIsNone(invalid.parent)
        self.assertIsNone(invalid.schema)
        self.assertEqual((123, 2), invalid.values)
        self.assertEqual(['Existing'], [row['Name'] for row in rows.children()])
        document.validate()

    def test_computed_fields_cannot_gain_stored_duplicates(self):
        document = ExampleDocument()
        row = document.root.add('Rows').add('Row', 'Example', 1)
        with self.assertRaises(ValueError):
            row.add('Index', 99)
        self.assertEqual(0, row['Index'])
        self.assertIsNone(row.child('Index'))
        document.validate()


if __name__ == '__main__':
    unittest.main()
