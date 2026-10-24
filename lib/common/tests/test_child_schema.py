"""Ownership metadata and explicit audits are independent from scalar access."""
from dataclasses import FrozenInstanceError
import unittest

from lib.common.model import Document, Element
from lib.common.schema import Child, Field, Record


class ChildSchemaTests(unittest.TestCase):
    def test_child_metadata_is_immutable_and_separate_from_fields(self):
        entry = Child('Rows', 'Rows', minimum=1)
        schema = Record('Owner', {'Name': Field('Name', 'text')}, children={'Rows': entry})
        with self.assertRaises(TypeError):
            schema.children['Other'] = entry
        with self.assertRaises(FrozenInstanceError):
            entry.minimum = 0
        with self.assertRaises(ValueError):
            Record('Invalid', {'Rows': Field('Rows')}, children={'Rows': entry})
        for values in ({'minimum': -1}, {'minimum': True}, {'minimum': 2, 'maximum': 1}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                Child('Rows', **values)

    def test_empty_declared_children_require_navigation(self):
        node = Element('Owner').bind_schema(Record('Owner', {}, children={'Rows': Child('Rows', 'Rows')}))
        self.assertIsNone(node.get('Rows'))
        rows = node.add('Rows')
        self.assertIn('Rows', node)
        self.assertIs(node.child('Rows'), rows)
        with self.assertRaises(TypeError):
            node['Rows']
        with self.assertRaises(TypeError):
            node.get('Rows')
        with self.assertRaises(ValueError):
            node.scalar('Rows')

    def test_full_audit_checks_declared_cardinality_and_bound_record_type(self):
        doc = Document()
        owner = doc.root.add('Owner').bind_schema(Record('Owner', {}, children={
            'Row': Child('Row', 'Row', minimum=1, maximum=2)}))
        with self.assertRaisesRegex(ValueError, 'requires 1..2 children'):
            doc.validate()
        row = owner.add('Row').bind_schema(Record('Row', {}))
        doc.validate()
        owner.add('Row')
        with self.assertRaisesRegex(ValueError, 'child count'):
            owner.add('Row')
        # Full audit also detects bypasses of the supported mutation API.
        extra = Element('Row')
        extra._parent = owner
        owner._items.append(extra)
        owner._touch(reordered=True)
        with self.assertRaisesRegex(ValueError, 'found 3'):
            doc.validate()
        extra.detach()
        row.bind_schema(Record('Wrong', {}))
        with self.assertRaisesRegex(ValueError, 'expected Row, found Wrong'):
            doc.validate()
