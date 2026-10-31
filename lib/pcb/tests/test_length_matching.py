"""Length-rule targets remain coherent during ordinary PCB data editing."""
from decimal import Decimal
import unittest
from unittest.mock import patch

from lib.common.model import Element
from lib.common.references import ReferenceError
from lib.pcb.formats.assembly.board_rules import assemble_rules
from lib.pcb.formats.assembly.routing_inputs import RoutingInputs
from lib.pcb.model import length_matching
from lib.pcb.model.definitions import NET
from lib.pcb.tests.test_core_assembly import fixture


def design(*, by_class=False):
    source = fixture()
    source.upgrades = RoutingInputs()
    if by_class:
        net_class = source.board.add('NetClasses').add('NetClass', 'Signals')
        for name, value in dict(CheckLength=True, FixedLength=12, LengthDelta=Decimal('.5'),
                                MinLength=8, MaxLength=16).items():
            net_class.add(name, value)
        source.board.one('Nets/Net').add('NetClass', 0)
        policy = source.board.add('LengthRules').add('LengthRule', 9)
    else:
        policy = source.board.add('MainLengthRule')
    for name, value in dict(Name='Matched', FixedLength=3, Delta=Decimal('.2'),
                            AnyError=False, NetClass=0 if by_class else -1,
                            Type=1 if by_class else 0).items():
        policy.add(name, value)
    row = policy.add('Rules').add('Rule', 0)
    for name, value in dict(NetId=73, Comp1=41, Pad1=5, Comp2=41, Pad2=12,
                            Length=Decimal('3.5'), Error=False).items():
        row.add(name, value)
    if not by_class:
        source.board.add('LengthRules')
    return assemble_rules(source)


class LengthMatchingTests(unittest.TestCase):
    def test_import_consumes_keys_into_named_policy_and_connection_records(self):
        result = design()
        policy = result.document.one('/Board/MainLengthRule')
        row = policy.one('Rules/Rule')
        core = result.routing.core
        self.assertIs(policy.schema, length_matching.POLICY)
        self.assertIs(row.schema, length_matching.CONNECTION)
        self.assertEqual((policy['Name'], policy['Delta'], row['Length']),
                         ('Matched', Decimal('.2'), Decimal('3.5')))
        self.assertIs(row['Net'], core.nets[73])
        self.assertIs(row['Pad1'], core.pads[41, 5])
        self.assertIs(row['Pad2'], core.pads[41, 12])
        self.assertIs(row['Component1'], core.components[41])
        self.assertEqual((row['NetId'], row['ComponentIndex1'], row['PadIndex2']), (0, 0, 1))
        self.assertEqual(row.values, ())
        for name in ('NetId', 'Comp1', 'Pad1', 'Comp2', 'Pad2'):
            self.assertIsNone(row.child(name))
        result.document.references.validate()

    def test_reorder_and_rename_follow_targets_without_recalculating_lengths(self):
        result = design()
        core, document = result.routing.core, result.document
        row = document.one('/Board/MainLengthRule/Rules/Rule')
        second = core.pads[41, 12]
        second.move_to(second.parent, 0)
        core.components[41]['RefDes'] = 'U2'
        core.nets[73]['Name'] = 'Data'
        self.assertIs(row['Pad2'], second)
        self.assertEqual(row['PadIndex2'], 0)
        self.assertEqual(row['Component2']['RefDes'], 'U2')
        self.assertEqual(row['Net']['Name'], 'Data')
        self.assertEqual(row['Length'], Decimal('3.5'))
        document.references.validate()

    def test_membership_and_net_changes_are_atomic_until_targets_are_disconnected(self):
        result = design()
        document, core = result.document, result.routing.core
        row = document.one('/Board/MainLengthRule/Rules/Rule')
        other = document.one('/Board/Nets').append(Element('Net', 'Other').bind_schema(NET))
        other.add('Enabled', True)
        with self.assertRaises(ReferenceError):
            row['Net'] = other
        with self.assertRaises(ReferenceError):
            row['Net'] = None
        with self.assertRaises(ReferenceError):
            core.pads[41, 5]['Net'] = None
        self.assertIs(row['Net'], core.nets[73])
        self.assertIs(row['Pad1'], core.pads[41, 5])
        row['Pad1'] = None
        core.pads[41, 5]['Net'] = None
        self.assertIsNone(row['Component1'])
        self.assertEqual(row['PadIndex1'], -1)
        row['Pad2'] = None
        row['Net'] = other
        self.assertIs(row['Net'], other)
        document.references.validate()

    def test_clone_and_copy_preserve_local_targets_and_removal_guards(self):
        result = design()
        document = result.document
        row = document.one('/Board/MainLengthRule/Rules/Rule')
        with self.assertRaises(ReferenceError):
            document.remove(row['Pad1'])
        clone = document.clone()
        copied = clone.one('/Board/MainLengthRule/Rules/Rule')
        self.assertIsNot(copied['Net'], row['Net'])
        self.assertIs(copied['Pad1']._owner(), clone)
        with self.assertRaises(ReferenceError):
            copied['Pad1'] = row['Pad1']
        duplicate = document.copy(row, parent=row.parent)
        self.assertIs(duplicate['Pad2'], row['Pad2'])
        document.remove(duplicate)
        document.remove(document.one('/Board/MainLengthRule'))
        document.references.validate()
        clone.references.validate()

    def test_new_records_bind_the_same_schemas_and_require_their_rule_scope(self):
        result = design()
        document = result.document
        policy = document.one('/Board/LengthRules').add('LengthRule')
        policy['Name'] = 'Additional'
        rows = policy.add('Rules')
        row = rows.add('Rule')
        row['Net'] = result.routing.core.nets[73]
        row['Pad1'] = result.routing.core.pads[41, 5]
        self.assertIs(policy.schema, length_matching.POLICY)
        self.assertIs(row.schema, length_matching.CONNECTION)
        self.assertIsNone(row['Pad2'])
        with self.assertRaises((ReferenceError, TypeError, ValueError)):
            row.move_to(document.one('/Board/Nets'))
        self.assertIs(row.parent, rows)
        document.references.validate()

    def test_local_edits_do_not_scan_the_whole_document_or_graph(self):
        result = design()
        document = result.document
        row = document.one('/Board/MainLengthRule/Rules/Rule')
        with patch.object(document.root, 'walk', side_effect=AssertionError('global tree scan')), \
                patch.object(type(document.references), '__iter__', side_effect=AssertionError('global graph scan')):
            row['Pad1'] = row['Pad2']
            row['Length'] = 8
            row['Pad2'] = None
            self.assertEqual(row['PadIndex1'], 1)

    def test_class_results_have_one_settings_owner_and_follow_class_edits_and_order(self):
        result = design(by_class=True)
        document, net_class = result.document, result.classes[0]
        results = net_class.one('LengthResults')
        row = results.one('Rules/Rule')
        self.assertIs(results.schema, length_matching.RESULTS)
        self.assertIs(row.schema, length_matching.CONNECTION)
        self.assertEqual(document.one('/Board/LengthRules').children(), [])
        for name in ('Name', 'FixedLength', 'Delta', 'NetClass', 'Type'):
            self.assertIsNone(results.child(name))
            self.assertNotIn(name, results.schema.fields)
        for name in ('MinLength', 'MaxLength'):
            self.assertIsNone(net_class.child(name))
            self.assertNotIn(name, net_class.schema.fields)
        with patch.object(document.root, 'walk', side_effect=AssertionError('global tree scan')), \
                patch.object(type(document.references), '__iter__', side_effect=AssertionError('global graph scan')):
            net_class['Name'] = 'Changed'
            net_class['FixedLength'] = 30
            row['Length'] = 14
            row['Pad1'] = row['Pad2']
        self.assertEqual((net_class['FixedLength'], row['Length']), (30, 14))
        self.assertIs(results.parent, net_class)
        document.references.validate()

    def test_class_result_attachments_and_moves_enforce_the_same_connection_constraints(self):
        result = design(by_class=True)
        document, net_class = result.document, result.classes[0]
        results = net_class.one('LengthResults')
        document.remove(results)
        results = net_class.add('LengthResults')
        row = results.add('Rules').add('Rule')
        row['Net'] = result.routing.core.nets[73]
        row['Pad1'] = result.routing.core.pads[41, 5]
        self.assertIs(results.schema, length_matching.RESULTS)
        with self.assertRaises(ReferenceError):
            row['Pad1']['Net'] = None
        with self.assertRaises((ReferenceError, TypeError, ValueError)):
            results.move_to(document.one('/Board'))
        with self.assertRaises((ReferenceError, TypeError, ValueError)):
            net_class.add('LengthResults')
        self.assertEqual(net_class.children('LengthResults'), [results])
        document.references.validate()

    def test_class_result_copy_clone_and_removal_preserve_current_targets(self):
        result = design(by_class=True)
        document, net_class = result.document, result.classes[0]
        row = net_class.one('LengthResults/Rules/Rule')
        clone = document.clone()
        copied = clone.one('/Board/NetClasses/NetClass/LengthResults/Rules/Rule')
        self.assertIsNot(copied['Pad1'], row['Pad1'])
        self.assertIs(copied['Pad1']._owner(), clone)
        with self.assertRaises((ReferenceError, TypeError, ValueError)):
            document.copy(net_class.one('LengthResults'), parent=document.one('/Board'))
        with self.assertRaises(ReferenceError):
            document.remove(net_class)
        document.one('/Board')['DefaultClass'] = None
        document.remove(net_class.one('LengthResults'))
        result.routing.core.nets[73]['Class'] = None
        document.remove(net_class)
        self.assertFalse(document.references.incoming(result.routing.core.pads[41, 5], role=length_matching.PAD_ROLES[0]))
        document.references.validate()
        clone.references.validate()

    def test_class_result_membership_is_guarded_during_net_class_and_row_edits(self):
        result = design(by_class=True)
        document, net_class = result.document, result.classes[0]
        row = net_class.one('LengthResults/Rules/Rule')
        net = result.routing.core.nets[73]
        with self.assertRaises(ReferenceError):
            net['Class'] = None
        self.assertIs(net['Class'], net_class)
        user = document.one('/Board/LengthRules').add('LengthRule')
        rows = user.add('Rules')
        row.move_to(rows)
        net['Class'] = None
        with self.assertRaises(ReferenceError):
            row.move_to(net_class.one('LengthResults/Rules'))
        self.assertIs(row.parent, rows)
        net['Class'] = net_class
        row.move_to(net_class.one('LengthResults/Rules'))
        document.references.validate()

    def test_aggregate_error_follows_current_rows_and_supports_indexed_search(self):
        result = design(by_class=True)
        document, net_class = result.document, result.classes[0]
        results = net_class.one('LengthResults')
        row = results.one('Rules/Rule')
        self.assertFalse(results['AnyError'])
        self.assertIsNone(results.child('AnyError'))
        self.assertEqual(document.select('/Board/NetClasses/NetClass/LengthResults[AnyError=true]'), [])
        row['Error'] = True
        self.assertTrue(results['AnyError'])
        self.assertEqual(document.select('/Board/NetClasses/NetClass/LengthResults[AnyError=true]'), [results])
        document.remove(row)
        self.assertFalse(results['AnyError'])
        self.assertEqual(document.select('/Board/NetClasses/NetClass/LengthResults[AnyError=true]'), [])
        with self.assertRaises(TypeError):
            results['AnyError'] = True


if __name__ == '__main__':
    unittest.main()
