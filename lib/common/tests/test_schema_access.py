"""Named access has ordinary mapping behavior and one authoritative value."""
import unittest

from lib import Document, Element, Index, Key, Property, ReferenceError
from lib.common.schema import Field, Record


class SchemaAccessTests(unittest.TestCase):
    def test_declared_choices_validate_edits_and_full_audits(self):
        choices = ['mm', 'mil', 'inch']
        field = Field('Units', 'text', choices=choices)
        choices.append('cm')
        self.assertEqual(field.choices, ('mm', 'mil', 'inch'))
        node = Element('Settings').bind_schema(Record('Settings', {'Units': field}))
        document = Document()
        document.root.append(node)
        node['Units'] = 'mil'
        with self.assertRaisesRegex(ValueError, 'must be one of'):
            node['Units'] = 'cm'
        self.assertEqual(node['Units'], 'mil')
        node.one('Units').set_values('invalid')  # Deliberately bypass named access.
        with self.assertRaisesRegex(ValueError, 'must be one of'):
            document.validate()

    def test_full_audit_checks_nonparameter_types_duplicates_and_required_presence(self):
        schema = Record('Typed', {
            'Name': Field('Name', 'text', required=True, default=''),
            'Count': Field('Count', 'integer', required=True),
        }, ('Name',))
        doc = Document()
        node = doc.root.append(Element('Typed', 'example').bind_schema(schema))
        with self.assertRaisesRegex(ValueError, 'required field Count'):
            doc.validate()
        node['Count'] = 3
        doc.validate()
        node.one('Count').set_values('invalid')  # Deliberately bypass named mutation.
        with self.assertRaisesRegex(TypeError, 'Count requires integer'):
            doc.validate()
        self.assertEqual(node.one('Count').values, ('invalid',))
        node['Count'] = 4
        duplicate = node.add('Scratch', 5)
        duplicate.kind = 'Count'  # Deliberately construct an invalid field occurrence.
        with self.assertRaisesRegex(ValueError, 'occurs more than once'):
            doc.validate()

    def test_scalar_union_preserves_typed_compatibility_choices(self):
        choice = Field('Choice', 'integer|text')
        for value in (0, 2, '', 'Unspecified'):
            choice.validate(value)
        for value in (True, 1.5, (), None):
            with self.subTest(value=value), self.assertRaises(TypeError):
                choice.validate(value)

    def record(self):
        schema = Record('Example', {
            'Name': Field('Name', 'text', required=True, default=''),
            'Count': Field('Count', 'integer'),
            'Enabled': Field('Enabled', 'boolean'),
            'Optional': Field('Optional', 'text', nullable=True),
        }, parameters=('Name',))
        return Element('Example', 'original').bind_schema(schema)

    def test_parameters_become_named_storage_and_only_project_back_to_arguments(self):
        record = self.record()
        self.assertEqual(record['Name'], 'original')
        self.assertEqual(record.values, ('original',))
        self.assertTrue(all(isinstance(item, Element) for item in record.items))
        record['Name'] = 'changed'
        self.assertEqual(record.values, ('changed',))
        record.set_argument(0, 'adapter edit')
        self.assertEqual(record['Name'], 'adapter edit')
        self.assertEqual(record.children('Name')[0].values, ('adapter edit',))

    def test_optional_defaults_none_and_presence_are_distinct(self):
        record = self.record()
        self.assertNotIn('Optional', record)
        self.assertIsNone(record.get('Optional'))
        self.assertEqual(record.get('Optional', 'fallback'), 'fallback')
        record['Optional'] = None
        self.assertIn('Optional', record)
        self.assertIsNone(record.get('Optional', 'fallback'))
        del record['Optional']
        self.assertNotIn('Optional', record)
        with self.assertRaises(KeyError):
            record['Optional']

    def test_false_zero_and_empty_text_are_present(self):
        record = self.record()
        for name, value in (('Name', ''), ('Count', 0), ('Enabled', False)):
            record[name] = value
            self.assertIn(name, record)
            self.assertEqual(record.get(name, 'fallback'), value)

    def test_invalid_assignments_and_required_deletion_do_not_change_values(self):
        record = self.record()
        for name, value in (('Name', 1), ('Count', True), ('Enabled', 0)):
            with self.subTest(name=name), self.assertRaises(TypeError):
                record[name] = value
        with self.assertRaises(TypeError):
            del record['Name']
        self.assertEqual(record['Name'], 'original')
        self.assertNotIn('Count', record)
        self.assertNotIn('Enabled', record)

    def test_unknown_reads_match_mapping_conventions_and_writes_are_validated(self):
        record = self.record()
        self.assertIsNone(record.get('Unknown'))
        self.assertEqual(record.get('Unknown', 3), 3)
        self.assertNotIn('Unknown', record)
        for operation in (lambda: record['Unknown'], lambda: record.set('Unknown', 1),
                          lambda: record.__delitem__('Unknown')):
            with self.assertRaises(KeyError):
                operation()

    def test_reflection_and_cloning_keep_definitions_without_sharing_data(self):
        record = self.record()
        self.assertEqual(record.schema.field('Name').kind, 'text')
        with self.assertRaises(TypeError):
            record.schema.fields['Other'] = Field('Other')
        copied = record.clone()
        copied.set('Name', 'copy')
        self.assertEqual(copied['Name'], 'copy')
        self.assertEqual(record['Name'], 'original')

    def linked(self, *, keyed=False):
        doc = Document()
        targets = doc.root.add('Targets')
        first = targets.append(self.record())
        second = targets.append(self.record())
        second['Name'] = 'other'
        link = doc.root.add('Link')
        label = link.add('Label', 'original')
        if keyed:
            doc.references.bind(link, first, Key(label, 'Name'), preserve=True)
        else:
            number = link.add('Index', 12)
            doc.references.bind(link, first, Index(number), Property(label, target_argument=0), preserve=True)
        return doc, first, second, label

    def test_named_rename_updates_dependent_property_without_rebuild_or_rekeying(self):
        doc, first, _, label = self.linked()
        first['Name'] = 'renamed'
        self.assertEqual(label.values, ('renamed',))
        self.assertEqual(doc.one('/Link/Index').values, (12,))

    def test_duplicate_key_rename_fails_before_changing_either_side(self):
        doc, first, _, label = self.linked(keyed=True)
        with self.assertRaisesRegex(ReferenceError, 'duplicate'):
            first['Name'] = 'other'
        self.assertEqual(first['Name'], 'original')
        self.assertEqual(label.values, ('original',))

    def test_property_consumers_follow_cloned_model_values(self):
        doc, first, _, label = self.linked()
        copied = doc.clone()
        copied.one('/Targets/Example[1]')['Name'] = 'copy'
        self.assertEqual(copied.one('/Link/Label').values, ('copy',))
        self.assertEqual(first['Name'], 'original')
        self.assertEqual(label.values, ('original',))

    def test_named_access_cannot_bypass_a_managed_parameter(self):
        doc = Document()
        target = doc.root.add('Targets').add('Target')
        schema = Record('Link', {'Target': Field('Target', 'integer', required=True, default=0)},
                        parameters=('Target',))
        link = doc.root.append(Element('Link', 0).bind_schema(schema))
        doc.references.bind(link, target, Index(link))
        with self.assertRaisesRegex(ValueError, 'reference-managed'):
            link['Target'] = 1
        self.assertEqual(link['Target'], 0)
        self.assertTrue(doc.references.manages(link))
        self.assertTrue(doc.references.manages(link.one('Target')))

    def test_named_access_cannot_silently_resolve_an_unknown_parameter(self):
        doc = Document()
        schema = Record('Link', {'Target': Field('Target', 'integer', required=True, default=99)},
                        parameters=('Target',))
        link = doc.root.append(Element('Link', 99).bind_schema(schema))
        doc.references.note(link, 'unknown target', Index(link), collections=())
        with self.assertRaisesRegex(ValueError, 'reference-managed'):
            link['Target'] = 0
        self.assertEqual(link['Target'], 99)
        copied = doc.clone()
        self.assertTrue(copied.references.unresolved_slot(copied.one('/Link/Target')))

    def test_adapter_tail_slot_does_not_alias_a_named_header(self):
        doc = Document()
        schema = Record('Link', {'Name': Field('Name', 'text', required=True)},
                        parameters=('Name',))
        link = doc.root.append(Element('Link', 'label', 99).bind_schema(schema))
        issue = doc.references.note(link, 'unknown target', Index(link, argument=1), collections=())
        self.assertTrue(doc.references.unresolved_slot(link, 1))
        self.assertFalse(doc.references.unresolved_slot(link.one('Name')))
        link['Name'] = 'renamed'
        doc.references.synchronize()
        copied = doc.clone()
        copied.references.synchronize()
        link.set_argument(1, 98)
        with self.assertRaisesRegex(ReferenceError, 'unresolved reference was edited'):
            doc.references.synchronize()
        doc.references.discard_issue(issue)
        self.assertFalse(doc.references.unresolved_slot(link, 1))


if __name__ == '__main__':
    unittest.main()
