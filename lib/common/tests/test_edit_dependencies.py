"""Named mutations preflight their affected guard and property graph."""
import unittest

from lib import Document, Element, Guard, Index, Key, Property, ReferenceError
from lib.common.schema import Field, Record


SCHEMA = Record('Item', {
    'Name': Field('Name', 'text', required=True),
    'Mode': Field('Mode', 'integer'),
    'Count': Field('Count', 'integer'),
}, parameters=('Name',))


def item(parent, name):
    return parent.append(Element('Item', name).bind_schema(SCHEMA))


class EditDependencyTests(unittest.TestCase):
    def chain(self):
        doc = Document()
        roots = doc.root.add('Items')
        first, other = item(roots, 'first'), item(roots, 'other')
        middle = item(doc.root.add('Items'), 'first')
        last = item(doc.root.add('Items'), 'first')
        reference = doc.references.bind(middle, first, Property(middle, target_argument=0), role='middle')
        doc.references.bind(last, middle, Property(last, target_argument=0), role='last')
        return doc, first, other, middle, last, reference

    def test_chained_properties_update_without_rebuild(self):
        doc, first, _, middle, last, _ = self.chain()
        first['Name'] = 'updated'
        self.assertEqual((first['Name'], middle['Name'], last['Name']), ('updated',)*3)
        doc.validate()

    def test_retarget_propagates_to_downstream_copies(self):
        doc, first, other, middle, last, reference = self.chain()
        doc.references.retarget(reference, other)
        self.assertEqual((middle['Name'], last['Name']), ('other', 'other'))
        first['Name'] = 'unrelated'
        self.assertEqual(last['Name'], 'other')

    def test_downstream_duplicate_key_rejects_the_whole_change(self):
        doc, first, _, middle, last, _ = self.chain()
        item(last.parent, 'duplicate')
        link = doc.root.add('Link', 'first')
        doc.references.bind(link, last, Key(link, 'Name'))
        with self.assertRaisesRegex(ReferenceError, 'duplicate'):
            first['Name'] = 'duplicate'
        self.assertEqual((first['Name'], middle['Name'], last['Name'], link.values[0]), ('first',)*4)

    def test_guard_mode_and_deletion_fail_before_changes_and_discard_unlocks_them(self):
        doc = Document()
        source = item(doc.root, 'source')
        source['Mode'] = 0
        target = doc.root.add('Targets').add('Target')
        number = source.add('Target', 0)
        reference = doc.references.bind(source, target, Index(number),
                                        guards=(Guard(source.one('Mode'), (0,)),))
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            source['Mode'] = 1
        with self.assertRaisesRegex(ValueError, 'reference-managed'):
            del source['Mode']
        self.assertEqual(source['Mode'], 0)
        doc.references.discard(reference)
        source['Mode'] = 1
        del source['Mode']
        self.assertNotIn('Mode', source)

    def test_guarded_named_header_and_clone_keep_independent_indexes(self):
        doc = Document()
        source = item(doc.root, 'first')
        target = doc.root.add('Targets').add('Target')
        number = source.add('Target', 0)
        doc.references.bind(source, target, Index(number), guards=(Guard(source, ('first',)),))
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            source['Name'] = 'changed'
        cloned = doc.clone()
        clone_source = cloned.one('/Item')
        cloned.references.discard(cloned.references.outgoing(clone_source)[0])
        clone_source['Name'] = 'copy'
        self.assertEqual(source['Name'], 'first')

    def test_downstream_guard_rejects_before_changing_master_or_copies(self):
        doc, first, _, middle, last, _ = self.chain()
        target = doc.root.add('Targets').add('Target')
        number = last.add('Target', 0)
        doc.references.bind(last, target, Index(number), guards=(Guard(last.one('Name'), ('first',)),))
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            first['Name'] = 'updated'
        self.assertEqual((first['Name'], middle['Name'], last['Name']), ('first',)*3)

    def test_retarget_type_failure_does_not_change_binding_or_field(self):
        doc = Document()
        roots = doc.root.add('Roots')
        numbers = Record('NumberItem', {**SCHEMA.fields, 'Count': Field('Count', 'number')}, ('Name',))
        first = roots.append(Element('Item', 'first').bind_schema(numbers))
        other = roots.append(Element('Item', 'other').bind_schema(numbers))
        first['Count'] = 1
        other['Count'] = 2.5
        source = item(doc.root, 'source')
        source['Count'] = 1
        reference = doc.references.bind(source, first, Property(source.one('Count'), 'Count'))
        with self.assertRaises(TypeError):
            doc.references.retarget(reference, other)
        self.assertIs(doc.references.get(reference.uid).target, first)
        self.assertEqual(source['Count'], 1)

    def test_binding_a_new_producer_updates_existing_consumers(self):
        doc = Document()
        first = item(doc.root.add('Items'), 'master')
        middle = item(doc.root.add('Items'), 'old')
        last = item(doc.root.add('Items'), 'old')
        doc.references.bind(last, middle, Property(last, target_argument=0))
        doc.references.bind(middle, first, Property(middle, target_argument=0))
        self.assertEqual((middle['Name'], last['Name']), ('master', 'master'))

    def test_copy_cycles_fail_without_registering_or_retargeting_any_link(self):
        doc, first, _, middle, last, reference = self.chain()
        count = len(doc.references)
        with self.assertRaisesRegex(ReferenceError, 'cycle'):
            doc.references.bind(first, last, Property(first, target_argument=0))
        self.assertEqual(len(doc.references), count)
        with self.assertRaisesRegex(ReferenceError, 'cycle'):
            doc.references.retarget(reference, last)
        self.assertIs(doc.references.get(reference.uid).target, first)
        first['Name'] = 'still editable'
        self.assertEqual((middle['Name'], last['Name']), ('still editable',)*2)

    def test_unreferenced_peer_cannot_make_an_existing_key_ambiguous(self):
        doc = Document()
        records = doc.root.add('Items')
        first, other = item(records, 'first'), item(records, 'other')
        link = doc.root.add('Link', 'first')
        doc.references.bind(link, first, Key(link, 'Name'))
        with self.assertRaisesRegex(ReferenceError, 'duplicate'):
            other['Name'] = 'first'
        self.assertEqual(other['Name'], 'other')
        self.assertEqual(link.values, ('first',))

    def test_retarget_duplicate_key_failure_preserves_targets_and_all_copies(self):
        doc, first, other, middle, last, reference = self.chain()
        item(last.parent, 'other')
        link = doc.root.add('Link', 'first')
        doc.references.bind(link, last, Key(link, 'Name'))
        with self.assertRaisesRegex(ReferenceError, 'duplicate'):
            doc.references.retarget(reference, other)
        self.assertIs(doc.references.get(reference.uid).target, first)
        self.assertEqual((middle['Name'], last['Name'], link.values[0]), ('first',)*3)

    def test_new_binding_cannot_overwrite_its_own_mode_guard(self):
        doc = Document()
        source = item(doc.root, 'source')
        source['Mode'] = 1
        target = doc.root.add('Targets').add('Target')
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            doc.references.bind(source, target, Index(source.one('Mode')),
                                guards=(Guard(source.one('Mode'), (1,)),))
        self.assertEqual(source['Mode'], 1)
        self.assertEqual(len(doc.references), 0)

    def test_binding_does_not_discard_an_unrelated_slotless_issue(self):
        doc = Document()
        source = doc.root.add('Link', 0)
        target = doc.root.add('Targets').add('Target')
        issue = doc.references.note(source, 'unknown relationship')
        doc.references.bind(source, target, Index(source))
        self.assertIn(issue, doc.references.issues)

    def test_unresolved_mode_guards_survive_clone_and_explicit_resolution(self):
        doc = Document()
        source = item(doc.root, 'source')
        source['Mode'] = 0
        number = source.add('Target', 99)
        target = doc.root.add('Targets').add('Target')
        guards = (Guard(source.one('Mode'), (0,)),)
        issue = doc.references.note(source, 'unknown target', Index(number), guards=guards)
        self.assertIs(doc.references.note(source, 'unknown target', Index(number), guards=guards), issue)
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            source['Mode'] = 1
        copied = doc.clone()
        copied.references.discard_issue(copied.references.issues[0])
        copied.one('/Item')['Mode'] = 1
        self.assertEqual(source['Mode'], 0)
        reference = doc.references.bind(source, target, Index(number), guards=guards)
        self.assertEqual(doc.references.issues, [])
        self.assertEqual(doc.references.unresolved_guard_consumers(source.one('Mode')), ())
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            source['Mode'] = 1
        doc.references.discard(reference)
        source['Mode'] = 1

    def test_empty_guarded_tuple_cannot_be_removed_or_grow(self):
        doc = Document()
        schema = Record('Vector', {'Mode': Field('Mode', 'tuple')})
        source = doc.root.append(Element('Vector').bind_schema(schema))
        mode = source.add('Mode')
        number = source.add('Target', 0)
        target = doc.root.add('Targets').add('Target')
        reference = doc.references.bind(source, target, Index(number), guards=(Guard(mode, ()),))
        with self.assertRaisesRegex(ReferenceError, 'arity'):
            source['Mode'] = (1,)
        with self.assertRaisesRegex(ValueError, 'reference-managed'):
            del source['Mode']
        doc.references.discard(reference)
        source['Mode'] = (1,)
        self.assertEqual(source['Mode'], (1,))

    def test_audit_detects_raw_detachment_of_an_unresolved_guard(self):
        doc = Document()
        source = item(doc.root, 'source')
        source['Mode'] = 0
        number = source.add('Target', 99)
        doc.references.note(source, 'unknown', Index(number), guards=(Guard(source.one('Mode'), (0,)),))
        mode = source.one('Mode')
        with self.assertRaisesRegex(ReferenceError, 'unresolved reference content'):
            mode.detach()
        source._items.remove(mode)
        mode._parent = None
        source._touch(reordered=True)
        with self.assertRaisesRegex(ReferenceError, 'guard is detached'):
            doc.validate()

    def test_advanced_rebuild_propagates_copies_regardless_of_binding_order(self):
        doc = Document()
        first = item(doc.root.add('Items'), 'first')
        middle = item(doc.root.add('Items'), 'first')
        last = item(doc.root.add('Items'), 'first')
        doc.references.bind(last, middle, Property(last, target_argument=0), preserve=True)
        doc.references.bind(middle, first, Property(middle, target_argument=0), preserve=True)
        first.one('Name').set_values('updated')
        doc.rebuild()
        self.assertEqual((middle['Name'], last['Name']), ('updated',)*2)

    def test_tuple_edit_can_swap_keys_through_different_copy_depths(self):
        doc = Document()
        members = (Field('X', 'integer', required=True), Field('Y', 'integer', required=True))
        holder = doc.root.append(Element('Holder').bind_schema(
            Record('Holder', {'Pair': Field('Pair', 'tuple', members=members)})))
        pair = holder.append(Element('Pair', 1, 2).bind_schema(
            Record('Pair', {field.name: field for field in members}, ('X', 'Y'))))
        schema = Record('Entry', {'Id': Field('Id', 'integer')})
        records = doc.root.add('Entries')
        left = records.append(Element('Entry').bind_schema(schema))
        right = records.append(Element('Entry').bind_schema(schema))
        middle = doc.root.add('Middle').append(Element('Entry').bind_schema(schema))
        for record, value in ((left, 1), (middle, 2), (right, 2)):
            record['Id'] = value
        doc.references.bind(left, pair, Property(left.one('Id'), 'X'))
        doc.references.bind(middle, pair, Property(middle.one('Id'), 'Y'))
        doc.references.bind(right, middle, Property(right.one('Id'), 'Id'))
        first_key, second_key = doc.root.add('Link', 1), doc.root.add('Link', 2)
        doc.references.bind(first_key, left, Key(first_key))
        doc.references.bind(second_key, right, Key(second_key))
        holder['Pair'] = (2, 1)
        self.assertEqual((left['Id'], right['Id']), (2, 1))
        self.assertEqual((first_key.values, second_key.values), ((2,), (1,)))

    def test_retarget_recomputes_a_key_changed_through_another_projection(self):
        doc = Document()
        source_schema = Record('Source', {'Name': Field('Name', 'text'), 'Lookup': Field('Lookup', 'text')})
        target_schema = Record('Target', {'Key': Field('Key', 'text'), 'Label': Field('Label', 'text')})
        records = doc.root.add('Items')
        source = records.append(Element('Item').bind_schema(source_schema))
        source['Name'], source['Lookup'] = 'X', 'Y'
        old = records.append(Element('Item').bind_schema(target_schema))
        old['Key'], old['Label'] = 'Y', 'X'
        new = records.append(Element('Item').bind_schema(target_schema))
        new['Key'], new['Label'] = 'X', 'Z'
        doc.references.bind(new, source, Property(new.one('Key'), 'Name'))
        reference = doc.references.bind(source, old, Key(source.one('Lookup'), 'Key'),
                                        Property(source.one('Name'), 'Label'))
        doc.references.retarget(reference, new)
        self.assertEqual((source['Name'], new['Key'], source['Lookup']), ('Z',)*3)
        doc.validate()
