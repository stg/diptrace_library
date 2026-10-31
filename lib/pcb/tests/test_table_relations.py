"""Documentation rows retain component identities through ordinary data edits."""
import unittest
from unittest.mock import patch

from lib.common.model import Value
from lib.common.references import Index, Property, ReferenceError
from lib.common.conversion import ConversionReport, import_diagnostics
from lib.pcb.model import table_records
from lib.pcb.model.table_relations import ROLE, MISSING
from lib.pcb.tests.test_table_model import fixture, design


def source(index=0):
    data = fixture()
    original = data.one('/Board/Components/Component')
    other = original.clone()
    other.one('Number').set_values(0)
    other.set_argument(1, Value('R5', 'symbol'))
    for pad in other.select('Pads/Pad'):
        pad.one('NetNumber').set_values(-1)
    original.parent.append(other)
    data.one('/Board/Tables/Table/Row_Components/RowCom[2]/pt').set_values(index)
    return data


def member(document):
    return document.one('/Board/Tables/Table[1]/RowComponents/Row[2]/Item')


class TableRelationshipTests(unittest.TestCase):
    def test_import_uses_positions_not_electrical_keys(self):
        document = design(source(1))
        row = member(document)
        first, second = document.select('/Board/Components/Component')
        self.assertIs(row['Component'], second)  # This component's source key was zero.
        self.assertEqual(row.values, (1,))
        self.assertIsNone(row.child('ComponentIndex'))
        self.assertIsNone(row.child(MISSING))
        self.assertFalse(any(isinstance(item, Value) for item in row.items))
        self.assertIs(first.one('Pattern/Pads/Pad[1]')['Net'], document.one('/Board/Nets/Net'))

    def test_reorder_rename_and_retarget_update_consumers_without_global_scans(self):
        document = design(source())
        row = member(document)
        first, second = document.select('/Board/Components/Component')
        probe = document.root.add('Probe', 0)
        document.references.bind(probe, row, Property(probe, 'ComponentIndex'), role='probe')
        with patch.object(document.root, 'walk', side_effect=AssertionError('global tree scan')), \
             patch.object(type(document.references), '__iter__', side_effect=AssertionError('global graph scan')):
            first['RefDes'] = 'R8'
            first.move_to(first.parent, 1)
            self.assertIs(row['Component'], first)
            self.assertEqual(probe.values, (1,))
            row['Component'] = second
            self.assertEqual(probe.values, (0,))
            row['Component'] = None
            self.assertEqual(probe.values, (-1,))
            self.assertIsNone(row['Component'])

    def test_foreign_wrong_disabled_and_duplicate_targets_fail_atomically(self):
        document = design(source())
        row, other = member(document), design(source())
        original = row['Component']
        second = document.one('/Board/Components/Component[2]')
        second['Enabled'] = False
        for target in (other.one('/Board/Components/Component[1]'), second, document.one('/Board/Nets/Net')):
            with self.subTest(target=target.path), self.assertRaises(ReferenceError):
                row['Component'] = target
            self.assertIs(row['Component'], original)
        with self.assertRaises(ReferenceError):
            document.references.bind(row, original, role=ROLE)
        self.assertIs(row['Component'], original)

    def test_disabling_or_deleting_a_referenced_component_is_rejected(self):
        document = design(source())
        row = member(document)
        # Disconnect pad assignments so it is the table that guards the component.
        first = row['Component']
        for net_member in tuple(document.select('/Board/Nets/Net/Pads/Item')):
            document.remove(net_member)
        with self.assertRaisesRegex(ReferenceError, 'table row'):
            first['Enabled'] = False
        self.assertTrue(first['Enabled'])
        with self.assertRaises(ReferenceError):
            document.remove(first)
        table = document.one('/Board/Tables/Table')
        with self.assertRaisesRegex(ReferenceError, 'table row'):
            table['Enabled'] = False
        self.assertTrue(table['Enabled'])
        row['Component'] = None
        first['Enabled'] = False
        document.remove(first)

    def test_clone_and_copy_preserve_identity_ownership(self):
        document = design(source())
        table = document.one('/Board/Tables/Table')
        copied = document.copy(table)
        self.assertIs(copied.one('RowComponents/Row[2]/Item')['Component'], member(document)['Component'])
        cloned = document.clone()
        self.assertIs(member(cloned)['Component'], cloned.one('/Board/Components/Component[1]'))
        self.assertIsNot(member(cloned)['Component'], member(document)['Component'])
        document.remove(copied)
        document.remove(table)
        self.assertEqual(document.references.incoming(document.one('/Board/Components/Component[1]'), role=ROLE), [])

    def test_row_moves_retain_links_and_reject_incompatible_destinations(self):
        document = design(source())
        table = document.one('/Board/Tables/Table')
        item = member(document)
        target = item['Component']
        empty_row = table.one('RowComponents/Row[1]')
        item.move_to(empty_row)
        self.assertIs(item['Component'], target)
        self.assertEqual(item['ComponentIndex'], 0)
        with self.assertRaises(ReferenceError):
            item.move_to(table.one('Cells'))
        with self.assertRaises(ReferenceError):
            table.move_to(document.one('/Board/Components'))
        self.assertIs(item.parent, empty_row)

    def test_new_members_use_identity_assignment_and_do_not_regenerate_cell_text(self):
        document = design(source())
        table = document.one('/Board/Tables/Table')
        new = table.one('RowComponents').add('Row').add('Item')
        self.assertIs(new.schema, table_records.MEMBER)
        self.assertIsNone(new['Component'])
        new['Component'] = document.one('/Board/Components/Component[2]')
        self.assertEqual(new['ComponentIndex'], 1)
        self.assertEqual(table.one('Cells/Cell[1]')['Text'], 'Current\n\nvalue')
        with self.assertRaises(TypeError):
            new.parent.add('Item', 0)
        with self.assertRaises(TypeError):
            new['ComponentIndex'] = 0

    def test_absent_target_stays_explicit_and_only_guards_its_scope(self):
        report = ConversionReport()
        document = import_diagnostics('asc')(design)(source(17), report=report)
        row = member(document)
        self.assertEqual((row[MISSING], row['ComponentIndex']), (17, 17))
        self.assertIn('unresolved-table-component', {notice.rule for notice in report.warnings})
        with self.assertRaisesRegex(ReferenceError, 'unresolved'):
            _ = row['Component']
        issue, = document.references.issues
        self.assertEqual(issue.collections, (document.one('/Board/Components'),))
        document.one('/Board/Components/Component[1]')['Value'] = 'Changed'
        document.one('/Board/Tables/Table/Cells/Cell[1]')['Text'] = 'Independent'
        with self.assertRaises(ReferenceError):
            document.one('/Board/Components/Component[1]').move_to(document.one('/Board/Components'), 1)
        with self.assertRaisesRegex(ValueError, 'reference-managed'):
            row[MISSING] = 0
        clone = document.clone()
        self.assertEqual(member(clone)[MISSING], 17)
        self.assertIs(clone.references.issues[0].source, member(clone))
        document.references.validate()
        clone.references.validate()

    def test_negative_source_selectors_mean_no_component(self):
        for value in (-1, -7):
            with self.subTest(value=value):
                document = design(source(value))
                row = member(document)
                self.assertIsNone(row['Component'])
                self.assertIsNone(row.child(MISSING))
                self.assertEqual(row['ComponentIndex'], -1)

    def test_resolving_or_disconnecting_unknown_slot_is_atomic_for_consumers(self):
        for disconnected in (False, True):
            with self.subTest(disconnected=disconnected):
                document = design(source(17))
                row = member(document)
                probe = document.root.add('Probe', 17)
                document.references.bind(probe, row, Property(probe, 'ComponentIndex'))
                target = None if disconnected else document.one('/Board/Components/Component[2]')
                with self.assertRaises(ReferenceError):
                    row['Component'] = design().one('/Board/Components/Component')
                self.assertEqual((row[MISSING], probe.values, len(document.references.issues)), (17, (17,), 1))
                row['Component'] = target
                self.assertIs(row['Component'], target)
                self.assertIsNone(row.child(MISSING))
                self.assertEqual(probe.values, (-1 if disconnected else 1,))
                self.assertEqual(document.references.issues, [])
                document.one('/Board/Components/Component[1]').move_to(document.one('/Board/Components'), 1)
                document.references.validate()

    def test_repair_refuses_to_remove_an_independently_referenced_unknown_value(self):
        document = design(source(17))
        row = member(document)
        probe = document.root.add('Probe', 0)
        document.references.bind(probe, row.one(MISSING), Index(probe))
        with self.assertRaises(ReferenceError):
            row['Component'] = document.one('/Board/Components/Component[1]')
        self.assertEqual((row[MISSING], row['ComponentIndex'], len(document.references.issues)), (17, 17, 1))


if __name__ == '__main__':
    unittest.main()
