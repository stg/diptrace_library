"""Typed nullable properties acquire and release values through ordinary links."""
import unittest

from lib.common.model import Document, Element
from lib.common.references import Property, ReferenceError
from lib.common.schema import Field, Record


def scalar(document, kind, value, *, nullable):
    schema = Record(kind, {'Value': Field('Value', 'number', nullable=nullable)}, parameters=('Value',))
    return document.root.append(Element(kind, value).bind_schema(schema))


class NullablePropertyTests(unittest.TestCase):
    def test_nullable_projection_follows_known_and_unavailable_values(self):
        document = Document()
        source = scalar(document, 'Source', 2, nullable=True)
        mirror = scalar(document, 'Mirror', None, nullable=True)
        document.references.bind(mirror, source, Property(mirror, 'Value'))
        self.assertEqual(mirror['Value'], 2)
        source['Value'] = None
        self.assertIsNone(mirror['Value'])
        source['Value'] = 3
        self.assertEqual(mirror['Value'], 3)
        document.validate()

    def test_nonnullable_dependents_reject_unavailability_atomically(self):
        document = Document()
        source = scalar(document, 'Source', 2, nullable=True)
        mirror = scalar(document, 'Mirror', 0, nullable=False)
        document.references.bind(mirror, source, Property(mirror, 'Value'))
        with self.assertRaises(ReferenceError):
            source['Value'] = None
        self.assertEqual((source['Value'], mirror['Value']), (2, 2))
        document.validate()

    def test_null_does_not_grant_untyped_or_wrong_typed_projection(self):
        document = Document()
        source = scalar(document, 'Source', 2, nullable=False)
        untyped = document.root.add('Untyped', None)
        with self.assertRaises(ReferenceError):
            document.references.bind(untyped, source, Property(untyped, 'Value'))
        schema = Record('Text', {'Value': Field('Value', 'text', nullable=True)}, parameters=('Value',))
        text = document.root.append(Element('Text', None).bind_schema(schema))
        with self.assertRaises(ReferenceError):
            document.references.bind(text, source, Property(text, 'Value'))
        self.assertIsNone(untyped.values[0])
        self.assertIsNone(text['Value'])
        self.assertEqual(tuple(document.references), ())


if __name__ == '__main__':
    unittest.main()
