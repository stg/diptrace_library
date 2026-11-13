"""Bulk checks preserve fresh validation and parameter-first diagnostics."""
import unittest

from lib import Document, Element
from lib.common.field_edits import preview_values
from lib.common.model import Value
from lib.common.schema import Field, Record
from lib.common.structural_edits import preview_structure
from unittest.mock import patch


class SchemaVectorAuditTests(unittest.TestCase):
    def test_value_preview_audits_slots_without_expanding_unchanged_fields(self):
        schema = Record('Row', {'X': Field('X', 'number'), 'Name': Field('Name', 'text')})
        row = Element('Row').bind_schema(schema)
        row['X'], row['Name'] = 2, 'unchanged'
        coordinate = row.one('X')
        handles = dict(row._content.handles)
        with patch.object(Record, 'validate_parameters', side_effect=AssertionError('facade audit')):
            with preview_values(((coordinate, (Value.of(-2),)),)):
                schema.validate_fields(row)
                self.assertEqual(row['X'], -2)
            with preview_values(((coordinate, (Value.of('bad'),)),)):
                with self.assertRaisesRegex(TypeError, 'X requires number'):
                    schema.validate_fields(row)
        self.assertEqual(dict(row._content.handles), handles)
        self.assertEqual(row['X'], 2)

    def test_preview_shape_and_tuple_values_are_checked_without_mutation(self):
        schema = Record('Row', {'Key': Field('Key', 'integer'),
            'Pair': Field('Pair', 'tuple', length=2, item_kind='number')}, parameters=('Key',))
        row = Element('Row', 1).bind_schema(schema)
        row['Pair'] = (2, 3)
        for field, supplied, error, message in (
                (row.one('Key'), (), ValueError, 'Key requires one named value'),
                (row.one('Key'), (Value.of(1), Value.of(2)), ValueError, 'Key requires one named value'),
                (row.one('Pair'), (Value.of(1),), ValueError, 'Pair requires 2 tuple values'),
                (row.one('Pair'), (Value.of(1), Value.of('bad')), TypeError, 'Pair item requires number')):
            with self.subTest(message=message), preview_values(((field, supplied),)):
                with self.assertRaisesRegex(error, message):
                    schema.validate_fields(row)
        schema.validate_fields(row)
        self.assertEqual(row['Pair'], (2, 3))
        self.assertEqual(row['Key'], 1)

    def test_structural_preview_still_checks_the_proposed_field_set(self):
        schema = Record('Row', {'Name': Field('Name', 'text', required=True)})
        row = Element('Row').bind_schema(schema)
        row['Name'] = 'present'
        field = row.one('Name')
        with preview_structure({row: ()}, {field: None}, {}):
            with self.assertRaisesRegex(ValueError, 'required field Name is absent'):
                schema.validate_fields(row)
        schema.validate_fields(row)

    def test_custom_parameter_validation_is_not_bypassed(self):
        class Special(Record):
            def validate_parameters(self, record):
                super().validate_parameters(record)
                if record['Key'] == 0:
                    raise ValueError('custom key constraint')
        schema = Special('Row', {'Key': Field('Key', 'integer')}, parameters=('Key',))
        row = Element('Row', 0).bind_schema(schema)
        with self.assertRaisesRegex(ValueError, 'custom key constraint'):
            schema.validate_fields(row)
        row['Key'] = 1
        schema.validate_fields(row)

    def test_required_nullable_zero_false_and_invalid_replacement_are_distinct(self):
        schema = Record('Row', {'Name': Field('Name', 'text', required=True),
            'Enabled': Field('Enabled', 'boolean'), 'Width': Field('Width', 'number', nullable=True)})
        row = Element('Row').bind_schema(schema)
        with self.assertRaisesRegex(ValueError, 'required field Name'):
            schema.validate_fields(row)
        row['Name'], row['Enabled'], row['Width'] = '', False, None
        schema.validate_fields(row)
        row['Width'] = 0
        schema.validate_fields(row)
        row.one('Width').set_values('invalid')
        with self.assertRaisesRegex(TypeError, 'Width requires number'):
            schema.validate_fields(row)

    def test_parameters_are_checked_first_and_previews_use_their_current_values(self):
        schema = Record('Row', {'Other': Field('Other', 'number', required=True),
            'Key': Field('Key', 'integer')}, parameters=('Key',))
        row = Element('Row', 1).bind_schema(schema)
        row['Other'] = 2
        row.one('Key').set_values('bad key')
        row.one('Other').set_values('bad other')
        with self.assertRaisesRegex(TypeError, 'Key requires integer'):
            schema.validate_fields(row)
        row.one('Key').set_values(1)
        row.one('Other').set_values(2)
        with preview_values(((row.one('Other'), (Value.of('bad'),)),)):
            with self.assertRaisesRegex(TypeError, 'Other requires number'):
                schema.validate_fields(row)
        schema.validate_fields(row)

    def test_private_duplicate_after_warm_checks_is_found_by_public_validation(self):
        document = Document()
        row = document.root.add('Row').bind_schema(Record('Row', {'Name': Field('Name', 'text')}))
        row['Name'] = 'first'
        document.validate()
        duplicate = Element('Name', 'second')
        duplicate._parent = row
        row._items.append(duplicate)
        with self.assertRaisesRegex(ValueError, 'more than once'):
            document.validate()


if __name__ == '__main__':
    unittest.main()
