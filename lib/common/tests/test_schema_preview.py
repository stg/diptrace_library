"""Compact field audits see the same prospective edits as ordinary fields."""
import unittest
from unittest.mock import patch

from lib import Document, Element
from lib.common.field_edits import PreparedSlots, preview_values
from lib.common.model import Value
from lib.common.schema import Child, Field, Record
from lib.common.structural_edits import preview_structure, preview_ordinals


class SchemaPreviewTests(unittest.TestCase):
    def test_prepared_slots_reuse_values_and_refresh_after_dependency_changes(self):
        schema = Record('Row', {name: Field(name, 'number', required=True)
                               for name in ('First', 'Second')}, parameters=('First', 'Second'))
        row = Element('Row', 1, 2).bind_schema(schema)
        row._compact_fields()
        first, second = row.one('First'), row.one('Second')
        overrides = {second._argument_owner(0): Value.of(20)}
        from lib.common import field_edits
        with preview_values(((first, (Value.of(10),)),)):
            prepared = PreparedSlots(overrides)
            with patch.object(field_edits, '_slot_changes', wraps=field_edits._slot_changes) as build:
                for unused in range(3):
                    with prepared:
                        self.assertEqual(row.values, (10, 20))
                    self.assertEqual(row.values, (10, 2))
                self.assertEqual(build.call_count, 1)
                overrides[second._argument_owner(0)] = Value.of(30)
                prepared.invalidate()
                with self.assertRaisesRegex(ValueError, 'preflight'):
                    with prepared:
                        self.assertEqual(row.values, (10, 30))
                        raise ValueError('preflight')
                self.assertEqual(build.call_count, 2)
                self.assertEqual(row.values, (10, 2))
        self.assertEqual(row.values, (1, 2))

    def test_empty_nested_structure_previews_keep_the_enclosing_order(self):
        document = Document()
        parent = document.root.add('Rows')
        first, second = parent.add('Row'), parent.add('Row')
        self.assertEqual(first.path, '/Rows[1]/Row[1]')
        with preview_structure({parent: (second, first)}, {}, {second: 0, first: 1}):
            with preview_structure({}, {}, {}), preview_ordinals({}):
                self.assertEqual(parent.children(), [second, first])
                self.assertEqual(first.path, '/Rows[1]/Row[2]')
                self.assertIs(first.parent, parent)
        self.assertEqual(parent.children(), [first, second])
        self.assertEqual(first.path, '/Rows[1]/Row[1]')

    def test_field_and_parameter_validation_reads_proposed_values(self):
        for compact in (False, True):
            for parameters in ((), ('Size',)):
                with self.subTest(compact=compact, parameters=parameters):
                    schema = Record('Row', {'Size': Field('Size', 'number', required=True,
                                                         default=1)}, parameters=parameters)
                    row = Element('Row').bind_schema(schema)
                    row['Size'] = 1
                    if compact:
                        row._compact_fields()
                    schema.validate_fields(row)
                    with preview_values(((row.one('Size'), (Value.of('bad'),)),)):
                        with self.assertRaises(TypeError):
                            schema.validate_fields(row)
                        if parameters:
                            with self.assertRaises(TypeError):
                                schema.validate_parameters(row)
                    schema.validate_fields(row)
                    self.assertEqual(row['Size'], 1)

    def test_prospective_removal_is_not_hidden_by_a_present_slot(self):
        for compact in (False, True):
            schema = Record('Row', {'Name': Field('Name', 'text', required=True)},
                            children={'Item': Child('Item', maximum=None)})
            document = Document()
            row = document.root.add('Row').bind_schema(schema)
            row['Name'] = 'first'
            item = row.add('Item')
            if compact:
                row._compact_fields()
            schema.validate_fields(row)
            with preview_structure({row: (item,)}, {}, {}):
                with self.assertRaisesRegex(ValueError, 'required field Name'):
                    schema.validate_fields(row)
            document.validate()


if __name__ == '__main__':
    unittest.main()
