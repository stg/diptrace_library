"""Compact records use the ordinary navigation, edit and relationship API."""
import gc
import unittest
import weakref

from lib.common.model import Document, Element, SourceSpan, Value
from lib.common.element_storage import FieldItems, RecordItems
from lib.common.references import Index, Property
from lib.common.schema import Child, Field, Record
from lib.common.structural_edits import DetachedSnapshot, preview_structure
from lib.common.field_edits import preview_values


ROW = Record('Row', {
    'Name': Field('Name', 'text', required=True),
    'Value': Field('Value', 'text', nullable=True),
    'Target': Field('Target', 'integer'),
    'Position': Field('Position', 'tuple', members=(Field('X', 'number'), Field('Y', 'number'))),
}, children={'Nested': Child('Nested')})


def row():
    node = Element('Row').bind_schema(ROW)
    node['Name'], node['Value'], node['Target'] = 'one', None, 0
    node['Position'] = (1, 2)
    return node


class RecordValueViewTests(unittest.TestCase):
    def test_parameter_replacement_retains_other_fields_children_and_metadata(self):
        schema = Record('Header', {'Key': Field('Key', 'integer'), 'Text': Field('Text', 'text')},
                        parameters=('Key',), children={'Nested': Child('Nested')})
        node = Element('Header', 1).bind_schema(schema)
        node['Text'] = 'kept'
        text = node.one('Text')
        text.source = SourceSpan('test', 3, 7)
        text.annotations['note'] = ['detail']
        identity = text.uid
        nested = node.add('Nested')
        storage = node._content.storage
        node.set_values(2)
        self.assertEqual(node.values, (2,))
        self.assertEqual(node['Text'], 'kept')
        self.assertIs(node.one('Text'), text)
        self.assertEqual(text.uid, identity)
        self.assertEqual(text.source, SourceSpan('test', 3, 7))
        self.assertEqual(text.annotations, {'note': ['detail']})
        self.assertIs(node.child('Nested'), nested)
        self.assertIs(nested.parent, node)
        self.assertIs(node._content.storage, storage)

    def test_parameter_replacement_updates_extra_arguments_without_repacking_fields(self):
        schema = Record('Header', {'Key': Field('Key', 'integer'), 'Text': Field('Text', 'text')},
                        parameters=('Key',))
        node = Element('Header', 1).bind_schema(schema)
        node['Text'] = 'kept'
        text = node.one('Text')
        storage = node._content.storage
        node.set_values(2, 'extra', False)
        self.assertEqual(node.values, (2, 'extra', False))
        self.assertEqual(tuple(value.value for value in node.items if isinstance(value, Value)), ('extra', False))
        node.set_values(3)
        self.assertEqual(node.values, (3,))
        self.assertIs(node.one('Text'), text)
        self.assertIs(node._content.storage, storage)
        schema.validate_fields(node)

    def test_owned_navigation_stays_current_across_field_and_record_changes(self):
        document = Document()
        node = document.root.append(row())._compact_fields()
        owned = node.add('Nested')
        self.assertEqual(node._record_children(), (node.one('Position'), owned))
        node['Target'] = 4
        del node['Value']
        node['Value'] = 'again'
        self.assertEqual(node._record_children(), (node.one('Position'), owned))
        owned.kind = 'Renamed'
        self.assertEqual(node.children('Nested'), [])
        self.assertEqual(node.children('Renamed'), [owned])
        owned.detach()
        self.assertEqual(node._record_children(), (node.one('Position'),))

    def test_warm_empty_record_cannot_hide_invalid_raw_content_from_validation(self):
        document = Document()
        node = document.root.append(Element('Row').bind_schema(Record('Empty', {})))._compact_fields()
        self.assertEqual(node.children(), [])
        node._content.order.append(object())
        with self.assertRaisesRegex(TypeError, 'record content'):
            document.validate()

    def test_decoder_slots_have_raw_field_semantics_before_schema_binding(self):
        schema = Record('Prefix', {'Name': Field('Name', 'text'), 'Items': Field('Items', 'tuple')})
        node = Element('Prefix')
        node._content = RecordItems(node, schema)
        node._content.import_value('Name', 'name')
        node._content.import_field('Items', (Value.of(7),))
        self.assertIsNone(node.schema)
        self.assertEqual(node['Name'], 'name')
        self.assertEqual(node['Items'], 7)
        self.assertEqual(node.scalar('Items'), 7)
        self.assertFalse(node._content.handles)
        node.bind_schema(schema)
        self.assertEqual(node['Items'], (7,))

    def test_adapter_arguments_preserve_metadata_without_allocating_a_field(self):
        node = Element('Row').bind_schema(ROW)
        value = Value(12, 'number', '%', '12%', SourceSpan('asc', 3, 6))
        node.add('Target', value)
        node._compact_fields(retain_debug=True)
        self.assertEqual(node._field_arguments('Target'), (value,))
        self.assertFalse(node._content.handles)
        handle = node.one('Target')
        with preview_values(((handle, (Value.of(25),)),)):
            self.assertEqual(node._field_arguments('Target'), (Value.of(25),))
        self.assertEqual(node._field_arguments('Target'), (value,))
        with self.assertRaises(LookupError):
            node._field_arguments('Absent')

    def test_unrelated_previews_keep_named_reads_lazy(self):
        first = row()._compact_fields()
        other = row()._compact_fields()
        field = other.one('Name')
        with preview_structure({}, {}, {}), preview_values(((field, (Value.of('proposed'),)),)):
            self.assertEqual(first['Name'], 'one')
            self.assertEqual(first.scalar('Target'), 0)
            self.assertFalse(first._content.handles)
            self.assertEqual(other['Name'], 'proposed')
            self.assertEqual(other.scalar('Name'), 'proposed')
        self.assertEqual(other['Name'], 'one')

    def test_field_position_lookup_does_not_expand_preceding_fields(self):
        node = row()._compact_fields()
        field = node.one('Target')
        self.assertEqual(node._items.index(field), 2)
        self.assertEqual(tuple(node._content.handles), (node._content.storage.layout.slots['Target'],))
        self.assertEqual(field._items.index(Value.of(0)), 0)
        with self.assertRaises(ValueError):
            node._items.index(field, 3)

    def test_parameter_projection_observes_prospective_field_edits(self):
        schema = Record('Header', {'Name': Field('Name', 'text')}, ('Name',))
        node = Element('Header', 'before').bind_schema(schema)._compact_fields()
        field = node.one('Name')
        with preview_values(((field, (Value.of('proposed'),)),)):
            self.assertEqual(node.values, ('proposed',))
            self.assertEqual(node.arguments[0].value, 'proposed')
        self.assertEqual(node.values, ('before',))

    def test_nested_parameter_previews_keep_optional_values_and_scalar_types(self):
        fields = (Field('X', 'number'), Field('Note', 'text', nullable=True), Field('Enabled', 'boolean'))
        schema = Record('Header', {field.name: field for field in fields}, ('X', 'Note', 'Enabled'))
        node = Element('Header', 1.25, None, False).bind_schema(schema)._compact_fields()
        x, enabled = node.one('X'), node.one('Enabled')
        with preview_values(((x, (Value.of(2.5),)),)):
            self.assertEqual(node.values, (2.5, None, False))
            self.assertEqual(enabled.values, (False,))
            with preview_values(((node, (Value.of(7.5), Value.of(None), Value.of(True))),)):
                self.assertEqual(node.values, (7.5, None, True))
                self.assertEqual((node['X'], node['Note'], node['Enabled']), (7.5, None, True))
                self.assertEqual(enabled.values, (True,))
            self.assertEqual(node.values, (2.5, None, False))
        self.assertEqual(node.values, (1.25, None, False))

    def test_schema_reset_rebinds_stored_fields_to_calculated_parameters(self):
        old = Record('Old', {'X': Field('X', 'number'), 'Y': Field('Y', 'number')}, ('X', 'Y'))
        new = Record('New', {
            'X': Field('X', 'number', getter=lambda node: 1),
            'Y': Field('Y', 'number', getter=lambda node: 2),
        }, ('X', 'Y'))
        node = Element('Point', 1, 2).bind_schema(old)._compact_fields()
        for name in old.parameters:
            node.one(name).detach()
        node._schema = None
        node.set_values()
        node.bind_schema(new)
        document = Document()
        document.root.append(node)
        document.validate()
        self.assertIs(node._content.storage.layout.schema, new)
        self.assertEqual(node.values, (1, 2))

    def test_existing_handle_is_adopted_and_updates_the_single_stored_value(self):
        node = row()
        old = node.one('Value')
        identity = old.uid
        node._compact_fields()
        self.assertIs(node.one('Value'), old)
        self.assertEqual(old.uid, identity)
        self.assertIsInstance(old._items, FieldItems)
        node['Value'] = 'changed'
        self.assertEqual(old.values, ('changed',))
        old.set_values('through the field')
        self.assertEqual(node['Value'], 'through the field')

    def test_named_reads_keep_unrequested_fields_unmaterialized(self):
        node = row()._compact_fields()
        gc.collect()
        self.assertEqual(len(node._items.handles), 0)
        self.assertEqual(node['Name'], 'one')
        self.assertIsNone(node.get('Value'))
        self.assertEqual(node.scalar('Position'), (1, 2))
        self.assertIn('Target', node)
        self.assertEqual(len(node._items.handles), 0)

    def test_owned_lookup_and_parameter_projection_do_not_materialize_fields(self):
        schema = Record('Parent', {'Name': Field('Name', 'text'), 'Value': Field('Value', 'number')},
                        ('Name',), children={'Nested': Child('Nested')})
        node = Element('Parent', 'one').bind_schema(schema)
        node['Value'] = 42
        owned = node.add('Nested')
        node._compact_fields()
        gc.collect()
        self.assertIs(node.child('Nested'), owned)
        self.assertEqual(node.values, ('one',))
        self.assertEqual(len(node._content.handles), 0)

    def test_full_audit_keeps_scalar_fields_lazy_and_checks_observed_identities(self):
        document = Document()
        node = document.root.append(row())._compact_fields()
        gc.collect()
        document.validate()
        self.assertEqual(len(node._content.handles), 0)
        self.assertFalse(node._content.identities)
        handle = node.one('Name')
        handle.uid
        document.validate()
        handle._uid = node.uid
        with self.assertRaisesRegex(ValueError, 'identity'):
            document.validate()

    def test_observed_uid_survives_handle_collection_and_document_lookup(self):
        doc = Document()
        node = doc.root.append(row())._compact_fields()
        handle = node.one('Value')
        identity = handle.uid
        observed = weakref.ref(handle)
        del handle
        gc.collect()
        self.assertIsNone(observed())
        self.assertEqual(doc.get(identity).uid, identity)
        self.assertIs(doc.get(identity).parent, node)

    def test_identity_lookup_and_field_removal_leave_other_fields_lazy(self):
        document = Document()
        node = document.root.append(row())._compact_fields()
        target = node.one('Target')
        identity = target.uid
        self.assertIs(document.get(identity), target)
        self.assertEqual(set(node._content.handles), {node._content.storage.layout.slots['Target']})
        target.detach()
        self.assertEqual(len(node._content.handles), 0)
        self.assertFalse(node._content.identities)
        self.assertIs(document.get(node.one('Name').uid).parent, node)

    def test_optional_removal_recreation_and_old_handle_are_independent(self):
        node = row()._compact_fields()
        old = node.one('Value')
        identity = old.uid
        del node['Value']
        self.assertIsNone(old.parent)
        self.assertNotIn('Value', node)
        old.set_values('detached')
        node['Value'] = 'new'
        self.assertEqual(old.values, ('detached',))
        self.assertEqual(node['Value'], 'new')
        self.assertNotEqual(node.one('Value').uid, identity)

    def test_failed_named_edits_and_required_removal_leave_data_unchanged(self):
        node = row()._compact_fields()
        with self.assertRaises(TypeError):
            node['Position'] = (1, 'bad')
        self.assertEqual(node['Position'], (1, 2))
        with self.assertRaises(TypeError):
            del node['Name']
        self.assertEqual(node['Name'], 'one')

    def test_owned_children_and_field_order_survive_moving_and_cloning(self):
        node = row()
        nested = node.add('Nested')
        node._compact_fields()
        value = node.one('Value')
        value.move_to(node, 0)
        self.assertIs(node.children()[0], value)
        copied = node.clone()
        self.assertEqual([child.kind for child in copied.children()], [child.kind for child in node.children()])
        self.assertIsNot(copied.one('Nested'), nested)
        self.assertEqual(copied['Value'], node['Value'])
        copied['Value'] = 'independent'
        self.assertIsNone(node['Value'])

    def test_notes_and_explicit_debug_metadata_survive_handle_collection(self):
        node = row()
        source = SourceSpan('example', 10, 20)
        handle = node.one('Target')
        handle.set_values(Value(0, 'number', '%', '0%', source))
        handle.source = source
        handle.annotations['notes'] = ['original']
        node._compact_fields(retain_debug=True)
        self.assertEqual(handle.arguments[0].unit, '%')
        self.assertIs(handle.arguments[0].source, source)
        new_source = SourceSpan('example', 20, 30)
        handle.source = new_source
        del handle
        gc.collect()
        self.assertIs(node.one('Target').source, new_source)
        self.assertEqual(node.one('Target').annotations['notes'], ['original'])
        copied = node.clone()
        copied.one('Target').annotations['notes'].append('copy')
        self.assertEqual(node.one('Target').annotations['notes'], ['original'])

    def test_new_notes_persist_without_pinning_the_field_handle(self):
        node = row()._compact_fields()
        handle = node.one('Value')
        handle.annotations['comment'] = 'keep'
        observed = weakref.ref(handle)
        del handle
        gc.collect()
        self.assertIsNone(observed())
        self.assertEqual(node.one('Value').annotations, {'comment': 'keep'})

    def test_raw_mutations_are_still_audited_behind_warm_caches(self):
        doc = Document()
        node = doc.root.append(row())._compact_fields()
        doc.validate()
        node.one('Target')._items[0] = Value('corrupt', 'string')
        with self.assertRaises(TypeError):
            doc.validate()
        node.one('Target').set_values(0)
        duplicate = Element('Target', 0)
        duplicate._parent = node
        node._items.append(duplicate)
        node._touch(reordered=True)
        with self.assertRaisesRegex(ValueError, 'more than once'):
            doc.validate()

    def test_parameter_projection_and_calculated_fields_keep_their_contract(self):
        schema = Record('Point', {'X': Field('X', 'number'), 'Y': Field('Y', 'number'),
                                'Total': Field('Total', 'number', getter=lambda n: n['X']+n['Y'])}, ('X', 'Y'))
        node = Element('Point', 2, 3).bind_schema(schema)._compact_fields()
        self.assertEqual(node.values, (2, 3))
        self.assertEqual(node['Total'], 5)
        self.assertIsNone(node.child('Total'))
        node.set_argument(1, 7)
        self.assertEqual(node.values, (2, 7))
        self.assertEqual(node['Total'], 9)

    def test_schema_rebinding_preserves_existing_handles_and_values(self):
        node = row()._compact_fields()
        handle = node.one('Value')
        expanded = Record('Expanded', {**ROW.fields, 'Extra': Field('Extra', 'text')}, children=ROW.children)
        node.bind_schema(expanded)
        self.assertIs(node.one('Value'), handle)
        node['Extra'] = 'additional'
        self.assertEqual(node['Extra'], 'additional')
        self.assertEqual(node['Name'], 'one')

    def test_binding_a_field_schema_materializes_structure_without_losing_values(self):
        node = row()._compact_fields()
        position = node.one('Position')
        point = Record('Point', {'X': Field('X', 'number'), 'Y': Field('Y', 'number')}, ('X', 'Y'))
        position.bind_schema(point)
        self.assertEqual(position['X'], 1)
        self.assertEqual(node['Position'], (1, 2))
        position['X'] = 4
        self.assertEqual(node['Position'], (4, 2))

    def test_snapshot_restores_schema_and_field_values_together(self):
        node = row()._compact_fields()
        snapshot = DetachedSnapshot(node)
        expanded = Record('Expanded', {**ROW.fields, 'Extra': Field('Extra', 'text')}, children=ROW.children)
        node.bind_schema(expanded)
        node['Value'], node['Extra'] = 'changed', 'new'
        snapshot.restore()
        self.assertIs(node.schema, ROW)
        self.assertIs(node._content.storage.layout.schema, ROW)
        self.assertIsNone(node['Value'])
        self.assertNotIn('Extra', node)

    def test_private_storage_corruption_is_audited_after_warming_handles(self):
        doc = Document()
        node = doc.root.append(row())._compact_fields()
        doc.validate()
        slot = node._content.storage.layout.slots['Value']
        node._content.storage._order.remove(slot)
        with self.assertRaisesRegex(ValueError, 'presence|order'):
            doc.validate()

    def test_dirty_state_belongs_to_each_field_after_its_handle_is_collected(self):
        node = row()
        for child in node.children():
            child._dirty = False
        node._dirty = False
        node._compact_fields()
        node['Value'] = 'edit'
        gc.collect()
        self.assertTrue(node.one('Value').changed)
        self.assertFalse(node.one('Name').changed)
        copied = node.clone()
        self.assertTrue(copied.one('Value').changed)
        self.assertFalse(copied.one('Name').changed)


class CompactReferenceTests(unittest.TestCase):
    def design(self):
        doc = Document()
        targets = doc.root.add('Targets')
        first, second = targets.add('Item', 'first'), targets.add('Item', 'second')
        owner = doc.root.append(row())
        label = doc.root.add('Label').bind_schema(Record('Label', {'Text': Field('Text', 'text')}))
        label['Text'] = 'one'
        doc.references.bind(owner, first, Index(owner.one('Target')), role='selected')
        doc.references.bind(label, owner, Property(label.one('Text'), name='Name'), role='label')
        doc.root._compact_fields(recursive=True)
        return doc, targets, first, second, owner, label

    def test_reorder_and_property_edits_update_existing_bound_handles(self):
        doc, targets, first, second, owner, label = self.design()
        target_field = owner.one('Target')
        first.move_to(targets, 1)
        self.assertEqual(owner['Target'], 1)
        self.assertEqual(target_field.values, (1,))
        owner['Name'] = 'renamed'
        self.assertEqual(label['Text'], 'renamed')
        with self.assertRaises(ValueError):
            label['Text'] = 'override'
        self.assertEqual(label['Text'], 'renamed')
        doc.validate()

    def test_clone_rebuilds_field_relationships_and_keeps_the_original_independent(self):
        doc, targets, first, second, owner, label = self.design()
        copied = doc.clone()
        copied.one('/Row')['Name'] = 'copy'
        self.assertEqual(copied.one('/Label')['Text'], 'copy')
        self.assertEqual(label['Text'], 'one')
        self.assertIsNot(copied.one('/Row/Target'), owner.one('Target'))
        copied.validate()
        doc.validate()

    def test_unresolved_guards_survive_compaction_and_clone(self):
        doc = Document()
        targets = doc.root.add('Targets')
        targets.add('Item')
        owner = doc.root.append(row())
        owner['Target'] = 99
        doc.references.note(owner, 'unresolved selection', Index(owner.one('Target')), collections=(targets,))
        doc.root._compact_fields(recursive=True)
        owner['Value'] = 'unrelated'
        with self.assertRaises(ValueError):
            owner['Target'] = 0
        copied = doc.clone()
        self.assertEqual(copied.one('/Row')['Target'], 99)
        copied.validate()


if __name__ == '__main__':
    unittest.main()
