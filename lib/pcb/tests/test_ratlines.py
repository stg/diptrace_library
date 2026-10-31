"""Ratline references remain coherent without recalculating electrical geometry."""
from decimal import Decimal
import unittest
from unittest.mock import patch

from lib.common.references import Property, ReferenceError
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.model import ratlines
from lib.pcb.tests.test_core_assembly import fixture


def source():
    data = fixture()
    row = data.board.add('Connections').add('Connection', 19)
    for name, value in dict(Enabled=True, Hidden=True, X1=1, Y1=2, X2=3, Y2=4,
                            Comp1=41, Pad1=5, Comp2=41, Pad2=12).items():
        row.add(name, value)
    return data


class RatlineTests(unittest.TestCase):
    def test_saved_keys_become_current_pad_identities_and_derived_views(self):
        result = assemble_core(source())
        document = result.document
        row = document.one('/Board/Ratlines/Ratline')
        self.assertIsNone(document.one('/Board').child('Connections'))
        self.assertIs(row.schema, ratlines.RATLINE)
        self.assertIs(row['Pad1'], result.pads[41, 5])
        self.assertIs(row['Pad2'], result.pads[41, 12])
        self.assertIs(row['Component1'], result.components[41])
        self.assertEqual((row['Id'], row['ComponentIndex1'], row['PadIndex2']), (0, 0, 1))
        self.assertTrue(row['Hidden'])
        self.assertNotIn('Selected', row.schema.fields)
        self.assertEqual(row.values, ())
        for name in ('Comp1', 'Comp2', 'Pad1', 'Pad2'):
            self.assertIsNone(row.child(name))
        document.references.validate()

    def test_reordering_and_edits_follow_identity_without_moving_supplied_geometry(self):
        result = assemble_core(source())
        document, pad = result.document, result.pads[41, 12]
        row = document.one('/Board/Ratlines/Ratline')
        with patch.object(document.root, 'walk', side_effect=AssertionError('global tree scan')), \
                patch.object(type(document.references), '__iter__', side_effect=AssertionError('global graph scan')):
            pad.move_to(pad.parent, 0)
            pad['X'] = 70
            pad['Net'] = None
            result.components[41]['RefDes'] = 'U2'
            row['Hidden'] = False
            row['X1'] = Decimal('1.5')
            self.assertIs(row['Pad2'], pad)
            self.assertEqual(row['PadIndex2'], 0)
            self.assertEqual(row['Component2']['RefDes'], 'U2')
            self.assertEqual((row['X2'], row['Y2']), (3, 4))
        # A ratline is a supplied guide, not an independent net-membership fact.
        self.assertIsNone(pad['Net'])
        document.references.validate()

    def test_clone_copy_foreign_targets_and_removal_constraints(self):
        result = assemble_core(source())
        document = result.document
        row = document.one('/Board/Ratlines/Ratline')
        clone = document.clone()
        copied = clone.one('/Board/Ratlines/Ratline')
        self.assertIsNot(copied['Pad1'], row['Pad1'])
        self.assertIs(copied['Pad1']._owner(), clone)
        with self.assertRaises(ReferenceError):
            copied['Pad1'] = row['Pad1']
        with self.assertRaises(ReferenceError):
            document.remove(row['Pad2'])
        duplicate = document.copy(row, parent=row.parent)
        self.assertIs(duplicate['Pad1'], row['Pad1'])
        document.remove(duplicate)
        document.remove(row)
        document.references.validate()
        clone.references.validate()

    def test_pad_reparenting_refreshes_derived_component_users_locally(self):
        result = assemble_core(source())
        document = result.document
        second = document.copy(result.components[41], fields={'RefDes': 'U2'})
        row = document.one('/Board/Ratlines/Ratline')
        observed = document.root.add('ObservedComponent', -1)
        document.references.bind(observed, row, Property(observed, 'ComponentIndex1'))
        self.assertEqual(observed.values, (0,))
        with patch.object(document.root, 'walk', side_effect=AssertionError('global tree scan')), \
                patch.object(type(document.references), '__iter__', side_effect=AssertionError('global graph scan')):
            row['Pad1'].move_to(second.one('Pattern/Pads'))
            self.assertIs(row['Component1'], second)
            self.assertEqual(observed.values, (1,))
            second.move_to(second.parent, 0)
            self.assertEqual(observed.values, (0,))
        document.references.validate()

    def test_new_attachments_share_schemas_and_enforce_board_scope(self):
        result = assemble_core(source())
        document = result.document
        rows = document.one('/Board/Ratlines')
        row = rows.add('Ratline')
        self.assertIs(row.schema, ratlines.RATLINE)
        row['Pad1'] = result.pads[41, 5]
        row['Pad2'] = None
        self.assertEqual(row['PadIndex2'], -1)
        with self.assertRaises((ReferenceError, TypeError, ValueError)):
            row.move_to(document.one('/Board/Nets'))
        self.assertIs(row.parent, rows)
        with self.assertRaises((ReferenceError, TypeError, ValueError)):
            rows.move_to(document.one('/Board/Components'))
        document.references.validate()

    def test_inactive_and_stale_positive_targets_are_removed_without_dummy_references(self):
        data = source()
        row = data.board.one('Connections/Connection')
        inactive = row.clone()
        inactive.one('Enabled').set_values(False)
        data.board.one('Connections').append(inactive)
        row.one('Pad1').set_values(99)
        result = assemble_core(data)
        self.assertEqual(result.document.one('/Board/Ratlines').children(), [])
        result.document.references.validate()

    def test_nonpositive_pad_selections_have_no_unused_component_copy(self):
        data = source()
        data.board.one('Connections/Connection/Pad1').set_values(0)
        data.board.one('Connections/Connection/Comp1').set_values(999)
        row = assemble_core(data).document.one('/Board/Ratlines/Ratline')
        self.assertIsNone(row['Pad1'])
        self.assertIsNone(row['Component1'])
        self.assertEqual(row['X1'], 1)


if __name__ == '__main__':
    unittest.main()
