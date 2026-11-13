"""Owned preparation rechecks edits without weakening public whole-tree audits."""
import unittest
from unittest.mock import patch

from lib import Document, Element, Index
from lib.common.schema import Child, Field, Record
from lib.common.validation_scope import checked_edits, _active, _finish_removals


ROW = Record('Row', {'Key': Field('Key', 'integer'), 'Name': Field('Name', 'text', required=True),
    'Flag': Field('Flag', 'boolean'), 'Nullable': Field('Nullable', 'number', nullable=True),
    'Missing': Field('Missing', 'number')}, parameters=('Key',))
ROWS = Record('Rows', {}, children={'Row': Child('Row', 'Row', maximum=None)})
LINK = Record('Link', {'N': Field('N', 'integer', required=True)})
LINKS = Record('Links', {}, children={'Link': Child('Link', 'Link', maximum=None)})
ROOT = Record('Root', {}, children={'Rows': Child('Rows', 'Rows'), 'Other': Child('Other', 'Rows'),
                                   'Links': Child('Links', 'Links')})


def row(key=1):
    result = Element('Row', key).bind_schema(ROW)
    result['Name'] = 'name'
    return result


def design():
    document = Document()
    document.root.bind_schema(ROOT)
    records = document.root.add('Rows').bind_schema(ROWS)
    first, second = records.append(row()), records.append(row(2))
    document.root.add('Other').bind_schema(ROWS)
    links = document.root.add('Links').bind_schema(LINKS)
    link = links.append(Element('Link').bind_schema(LINK))
    link['N'] = 0
    document.references.bind(link, first, Index(link.one('N')))
    document._automatic_structure = False
    return document, first, second, link


class ValidationScopeTests(unittest.TestCase):
    def tearDown(self):
        self.assertIsNone(_active.get())

    def test_only_changed_records_and_ancestors_need_the_second_schema_audit(self):
        document, first, second, _ = design()
        with patch.object(document, '_validate_record', wraps=document._validate_record) as audit:
            with checked_edits(document):
                audit.reset_mock()  # The complete entry audit has run.
                first['Name'] = 'changed'
                first['Key'], first['Flag'], first['Nullable'] = 0, False, None
            checked = [call.args[0] for call in audit.call_args_list]
        self.assertIn(first, checked)
        self.assertNotIn(second, checked)
        self.assertIs(first['Flag'], False)
        self.assertIsNone(first['Nullable'])
        self.assertEqual(first['Key'], 0)
        sentinel = object()
        self.assertIs(first.get('Missing', sentinel), sentinel)
        document.validate()

    def test_invalid_changed_fields_and_removed_required_parameters_are_rejected(self):
        for operation, error in ((lambda node: node.one('Name').set_values(3), TypeError),
                                 (lambda node: node.one('Key').detach(), ValueError)):
            with self.subTest(error=error):
                document, first, _, _ = design()
                with self.assertRaises(error), checked_edits(document):
                    operation(first)

    def test_incoming_subtrees_are_checked_including_changes_made_before_attachment(self):
        document, _, _, _ = design()
        new = row(3)
        new.one('Name').set_values(3)
        with self.assertRaisesRegex(TypeError, 'Name requires text'), checked_edits(document):
            document.root.one('Rows').append(new)

    def test_import_constructor_attachment_also_records_new_owned_content(self):
        document, _, _, _ = design()
        new = row(3)
        new.one('Name').set_values(3)
        with self.assertRaisesRegex(TypeError, 'Name requires text'), checked_edits(document):
            document.root.one('Rows')._append_import(new)

    def test_moves_and_reorders_keep_identity_and_finish_reference_projection(self):
        document, first, second, link = design()
        records = document.root.one('Rows')
        with checked_edits(document):
            first.move_to(records, 1)
        self.assertEqual(link['N'], 1)
        self.assertIs(document.references.outgoing(link)[0].target, first)
        with checked_edits(document):
            second.move_to(document.root.one('Other'))
        self.assertEqual(link['N'], 0)
        document.validate()

    def test_observed_incoming_record_or_field_ids_receive_global_duplicate_checks(self):
        for field in (False, True):
            document, first, _, _ = design()
            original = first.one('Name') if field else first
            known = original.uid
            new = row(3)
            target = new.one('Name') if field else new
            target._uid = known
            target.uid  # Record an observed field identity in compact storage.
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'duplicate element identity'):
                with checked_edits(document):
                    document.root.one('Rows').append(new)

    def test_schema_rebinding_is_a_change_even_without_a_value_edit(self):
        document, first, _, _ = design()
        replacement = Record('Row', {**ROW.fields, 'Extra': Field('Extra', 'number', required=True)}, ROW.parameters)
        with self.assertRaisesRegex(ValueError, 'required field Extra is absent'), checked_edits(document):
            first.bind_schema(replacement)

    def test_public_validation_still_sees_private_corruption_during_a_scope(self):
        document, _, second, _ = design()
        with self.assertRaisesRegex(TypeError, 'Name requires text'):
            with checked_edits(document):
                slot = second._content.storage.layout.slots['Name']
                second._content.storage._values[slot] = 23
                document.validate()

    def test_bound_attachment_checks_its_prebuilt_descendants(self):
        document, first, _, _ = design()
        nested = Record('Nested', {'Name': Field('Name', 'text', required=True)})
        link_schema = Record('Link', LINK.fields, children={'Nested': Child('Nested', 'Nested')})
        link = Element('Link').bind_schema(link_schema)
        link['N'] = 0
        detail = link.add('Nested').bind_schema(nested)
        detail['Name'] = 'name'
        detail.one('Name').set_values(23)
        with self.assertRaisesRegex(TypeError, 'Name requires text'), checked_edits(document):
            document.references._attach_bound(document.root.one('Links'), link, first, Index(link.one('N')))

    def test_live_documents_are_not_a_checked_preparation_interface(self):
        document, _, _, _ = design()
        document._automatic_structure = True
        with self.assertRaisesRegex(ValueError, 'adapter-owned view'), checked_edits(document):
            self.fail('live document entered an owned preparation scope')

    def test_removal_completion_rechecks_parent_constraints(self):
        document, first, _, _ = design()
        document._synchronize(force=False)
        first.one('Name').detach()
        with self.assertRaisesRegex(ValueError, 'required field Name is absent'):
            _finish_removals(document, (first,))


if __name__ == '__main__':
    unittest.main()
