"""Storage contracts required by the compact record/field facade."""
from decimal import Decimal
import unittest

from lib.common.record_storage import RecordLayout, RecordStorage
from lib.common.schema import Field, MISSING, Record


FIELDS = (
    Field('Name', 'text', required=True),
    Field('Value', 'text', nullable=True, default='default'),
    Field('Enabled', 'boolean'),
    Field('Count', 'integer'),
    Field('Position', 'tuple', members=(Field('X', 'number'), Field('Y', 'number'))),
    Field('Calculated', 'text', getter=lambda node: 'computed'),
)
SCHEMA = Record('StorageExample', {field.name: field for field in FIELDS})


class RecordStorageTests(unittest.TestCase):
    def test_integral_or_text_values_keep_exact_integer_identity(self):
        for kind in ('integer|text', 'text|integer'):
            with self.subTest(kind=kind):
                schema = Record('Choice', {'Type': Field('Type', kind)})
                storage = RecordStorage(schema, {'Type': Decimal('9007199254740993')})
                self.assertEqual(storage['Type'], 9007199254740993)
                self.assertIs(type(storage['Type']), int)
                storage['Type'] = 'named'
                self.assertEqual(storage['Type'], 'named')
                storage['Type'] = 2.0
                self.assertIs(type(storage['Type']), int)
                handle = storage.field('Type')
                storage.pop('Type')
                handle.value = Decimal('9007199254740993')
                self.assertEqual(handle.value, 9007199254740993)
                self.assertIs(type(handle.value), int)
        schema = Record('Number', {'Value': Field('Value', 'integer|number')})
        self.assertEqual(RecordStorage(schema, {'Value': Decimal('1.5')})['Value'], 1.5)

    def test_homogeneous_integer_tuples_keep_ids_beyond_float_precision(self):
        schema = Record('Ids', {'Values': Field('Values', 'tuple', item_kind='integer')})
        store = RecordStorage(schema, {'Values': (Decimal('9007199254740993'),)})
        self.assertEqual(store['Values'], (9007199254740993,))
        self.assertIs(type(store['Values'][0]), int)
        store.validate()

    def test_numeric_payloads_use_floats_without_rounding_integral_identities(self):
        storage = RecordStorage(SCHEMA, {'Name': 'R1', 'Count': Decimal('9007199254740993'),
                                       'Position': (Decimal('.1'), Decimal('.2'))})
        self.assertEqual(storage['Count'], 9007199254740993)
        self.assertIs(type(storage['Count']), int)
        self.assertEqual(storage['Position'], (.1, .2))
        self.assertTrue(all(type(value) is float for value in storage['Position']))
        self.assertEqual(storage.field('Position').value, (.1, .2))
        with self.assertRaises(TypeError):
            storage._store(storage.layout.slots['Count'], Decimal('1.5'))
        self.assertEqual(storage['Count'], 9007199254740993)

    def test_layout_is_shared_and_omits_calculated_values(self):
        left, right = RecordStorage(SCHEMA), RecordStorage(SCHEMA)
        self.assertIs(left.layout, right.layout)
        self.assertIs(left.layout, RecordLayout.for_schema(SCHEMA))
        self.assertNotIn('Calculated', left.layout.slots)
        with self.assertRaises(TypeError):
            left['Calculated'] = 'override'
        with self.assertRaises(TypeError):
            left.layout.slots['Other'] = 20

    def test_presence_is_independent_from_defaults_and_false_values(self):
        storage = RecordStorage(SCHEMA, {'Name': '', 'Enabled': False, 'Count': 0})
        self.assertNotIn('Value', storage)
        self.assertEqual(storage.get('Value', 'fallback'), 'fallback')
        with self.assertRaises(KeyError):
            storage['Value']
        storage['Value'] = None
        self.assertIn('Value', storage)
        self.assertIsNone(storage['Value'])
        self.assertEqual(storage['Name'], '')
        self.assertIs(storage['Enabled'], False)
        self.assertEqual(storage['Count'], 0)
        self.assertIsNone(storage.pop('Value'))
        self.assertNotIn('Value', storage)
        storage.validate()

    def test_named_reads_do_not_allocate_handles(self):
        storage = RecordStorage(SCHEMA, {'Name': 'R1', 'Value': '10k'})
        self.assertEqual(storage['Value'], '10k')
        self.assertEqual(dict(storage.items()), {'Name': 'R1', 'Value': '10k'})
        self.assertIsNone(storage._handles)

    def test_live_handle_follows_changes_in_both_directions(self):
        storage = RecordStorage(SCHEMA, {'Name': 'R1', 'Value': '10k'})
        handle = storage.field('Value')
        self.assertIs(handle, storage.field('Value'))
        storage['Value'] = '22k'
        self.assertEqual(handle.value, '22k')
        handle.value = '47k'
        self.assertEqual(storage['Value'], '47k')
        self.assertIs(handle, storage.field('Value'))
        storage.validate()

    def test_removed_handle_does_not_alias_a_recreated_field(self):
        storage = RecordStorage(SCHEMA, {'Name': 'R1', 'Value': '10k'})
        old = storage.field('Value')
        storage.pop('Value')
        self.assertFalse(old.attached)
        self.assertEqual(old.value, '10k')
        storage['Value'] = '22k'
        new = storage.field('Value')
        self.assertIsNot(old, new)
        old.value = 'detached edit'
        self.assertEqual(storage['Value'], '22k')
        self.assertEqual(old.value, 'detached edit')

    def test_reattachment_preserves_the_handle_without_a_value_backup(self):
        left = RecordStorage(SCHEMA, {'Name': 'R1', 'Value': '10k'})
        right = RecordStorage(SCHEMA, {'Name': 'R2'})
        handle = left.field('Value')
        left.pop('Value')
        right.attach(handle)
        self.assertIs(right.field('Value'), handle)
        self.assertIs(handle._detached, MISSING)
        handle.value = '22k'
        self.assertEqual(right['Value'], '22k')
        self.assertNotIn('Value', left)

    def test_failed_reattachment_preserves_both_records_and_the_detached_value(self):
        source = RecordStorage(SCHEMA, {'Name': 'R1', 'Value': '10k'})
        handle = source.field('Value')
        source.pop('Value')
        strict = Record('Strict', {'Value': Field('Value', 'integer')})
        target = RecordStorage(strict)
        with self.assertRaises(TypeError):
            target.attach(handle)
        self.assertFalse(handle.attached)
        self.assertEqual(handle.value, '10k')
        self.assertNotIn('Value', source)
        self.assertNotIn('Value', target)

    def test_tuple_values_keep_named_validation_and_float_normalization(self):
        storage = RecordStorage(SCHEMA, {'Name': 'R1'})
        storage['Position'] = (1.25, Decimal('2.50'))
        self.assertEqual(storage['Position'], (Decimal('1.25'), Decimal('2.50')))
        for invalid in ((1,), (1, 'bad'), (1, float('inf'))):
            with self.subTest(invalid=invalid), self.assertRaises((TypeError, ValueError)):
                storage['Position'] = invalid
            self.assertEqual(storage['Position'], (Decimal('1.25'), Decimal('2.50')))

    def test_group_assignment_is_atomic_and_preserves_field_order(self):
        storage = RecordStorage(SCHEMA, {'Name': 'R1', 'Count': 2})
        before = tuple(storage.items())
        with self.assertRaises(TypeError):
            storage.update({'Name': 'R2', 'Count': 'bad'})
        self.assertEqual(tuple(storage.items()), before)
        storage.update({'Value': '10k', 'Name': 'R3'})
        self.assertEqual([name for name, value in storage.items()], ['Name', 'Count', 'Value'])

    def test_clone_has_independent_presence_values_handles_and_order(self):
        source = RecordStorage(SCHEMA, {'Name': 'R1', 'Value': '10k'})
        original = source.field('Value')
        copied = source.clone()
        self.assertIs(copied.layout, source.layout)
        self.assertIsNone(copied._handles)
        copied.field('Value').value = '22k'
        source.pop('Value')
        self.assertEqual(copied['Value'], '22k')
        self.assertEqual(original.value, '10k')
        self.assertNotIn('Position', copied)
        source.validate()
        copied.validate()

    def test_required_fields_and_unknown_names_stay_strict(self):
        storage = RecordStorage(SCHEMA)
        with self.assertRaisesRegex(ValueError, 'Name'):
            storage.validate()
        storage['Name'] = 'R1'
        with self.assertRaises(TypeError):
            storage.pop('Name')
        with self.assertRaises(KeyError):
            storage['Unknown'] = 1

    def test_validation_reads_actual_values_even_after_handle_lookup(self):
        storage = RecordStorage(SCHEMA, {'Name': 'R1', 'Count': 2})
        handle = storage.field('Count')
        storage._values[storage.layout.slots['Count']] = 'corrupt'
        self.assertEqual(handle.value, 'corrupt')
        with self.assertRaises(TypeError):
            storage.validate()
        storage._values[storage.layout.slots['Count']] = 2
        storage._order.append(storage.layout.slots['Count'])
        with self.assertRaisesRegex(ValueError, 'presence'):
            storage.validate()

    def test_validation_audits_a_corrupted_handle_cache(self):
        storage = RecordStorage(SCHEMA, {'Name': 'R1', 'Count': 2})
        handle = storage.field('Count')
        handle._slot = storage.layout.slots['Name']
        with self.assertRaisesRegex(ValueError, 'handle'):
            storage.validate()

    def test_untyped_tuple_payloads_cannot_introduce_mutable_or_nonfinite_facts(self):
        schema = Record('Tuple', {'Values': Field('Values', 'tuple')})
        storage = RecordStorage(schema, {'Values': (1, 'text')})
        for values in (([],), ({'name': 1},), (Decimal('NaN'),), (float('inf'),)):
            with self.subTest(values=values), self.assertRaises((TypeError, ValueError)):
                storage['Values'] = values
            self.assertEqual(storage['Values'], (1, 'text'))
        storage._values[0] = ([],)
        with self.assertRaises(TypeError):
            storage.validate()


if __name__ == '__main__':
    unittest.main()
