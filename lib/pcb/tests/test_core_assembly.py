"""DIP import consumes saved keys rather than treating them as array positions."""
from types import SimpleNamespace
import unittest

from lib.common.model import Element
from lib.common.footprint_objects import new_pattern, new_pad
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.formats.dip.binary import DipError


def fixture(*, disagree=False):
    root = Element('')
    board = root.add('Board')
    components, nets = board.add('Components'), board.add('Nets')
    component = components.add('Component')
    for name, value in (('Number', 41), ('Name', 'Device'), ('RefDes', 'U1'),
                        ('Enabled', True), ('X', 0), ('Y', 0), ('Angle', 0)):
        component.add(name, value)
    pattern = component.append(new_pattern('Package'))
    pads = pattern.one('Pads')
    for index, key in enumerate((0, 5, 12, 0)):
        pad = pads.append(new_pad(str(index), index=index))
        pad['Number_New'] = key
        pad.add('NetNumber', 73 if 0 < index < 3 else 0)
    net = nets.add('Net')
    net.add('Number', 73)
    net.add('Enabled', True)
    net.add('Name', 'Supply')
    net.add('Pads').add('Item', 41, 12 if disagree else 5)
    if disagree:
        pads.children('Pad')[2].one('NetNumber').set_values(-1)
    return SimpleNamespace(root=root, board=board)


class CoreAssemblyTests(unittest.TestCase):
    def test_unused_repeated_numbers_keep_all_components_and_local_pad_relationships(self):
        decoded = fixture()
        first = decoded.board.one('Components/Component')
        first.add('InternalConnection_Records').add('pt', 12, 5)
        decoded.board.one('Nets/Net/Pads/Item').detach()
        for pad in first.select('Pattern/Pads/Pad'):
            pad.one('NetNumber').set_values(-1)
        second = first.clone()
        second.one('RefDes').set_values('U2')
        first.parent.append(second)
        result = assemble_core(decoded)
        self.assertEqual(result.components.records, (first, second))
        self.assertEqual([part['Number'] for part in result.components.records], [0, 1])
        self.assertEqual(len(result.pads.records), 4)
        for component in result.components.records:
            pair = component.one('IntConRecords/Item')
            self.assertIs(pair['Pad1'], component.one('Pattern/Pads/Pad[2]'))
            self.assertIs(pair['Pad2'], component.one('Pattern/Pads/Pad[1]'))
        with self.assertRaisesRegex(DipError, 'ambiguous saved component reference'):
            result.components[41]
        result.document.references.validate()

    def test_an_actually_ambiguous_external_pad_reference_still_fails_before_binding(self):
        decoded = fixture()
        first = decoded.board.one('Components/Component')
        second = first.clone()
        second.one('RefDes').set_values('U2')
        first.parent.append(second)
        with self.assertRaisesRegex(DipError, 'ambiguous saved net pad reference'):
            assemble_core(decoded)
        self.assertEqual(first['Number'], 41)
        self.assertEqual(second['Number'], 41)
        self.assertIsNone(decoded.root._document)

    def test_compound_pad_keys_can_resolve_without_a_unique_component_number(self):
        decoded = fixture()
        first = decoded.board.one('Components/Component')
        second = first.clone()
        second.one('RefDes').set_values('U2')
        for pad, key in zip(second.select('Pattern/Pads/Pad')[1:-1], (25, 26)):
            pad.one('Number_New').set_values(key)
        first.parent.append(second)
        result = assemble_core(decoded)
        member = result.document.one('/Board/Nets/Net/Pads/Item')
        self.assertIs(member['Pad'], first.one('Pattern/Pads/Pad[1]'))
        self.assertIs(result.pads[41, 25], second.one('Pattern/Pads/Pad[1]'))
        self.assertEqual(len(result.components.records), 2)
        result.document.references.validate()

    def test_saved_keys_are_consumed_and_unlisted_assignment_stays_unlisted(self):
        decoded = fixture()
        result = assemble_core(decoded)
        document = result.document
        component, net = result.components[41], result.nets[73]
        first, second = result.pads[41, 5], result.pads[41, 12]
        self.assertEqual(component['Number'], 0)
        self.assertEqual(net['Number'], 0)
        self.assertEqual(component.one('Pattern/Pads').children(), [first, second])
        self.assertEqual(net.one('Pads/Item').values, (0, 0))
        self.assertIs(net.one('Pads/Item')['Pad'], first)
        self.assertIs(first['Net'], net)
        self.assertIs(second['Net'], net)
        self.assertEqual(len(net.select('Pads/Item')), 1)
        self.assertEqual(len(document.references.outgoing(second, role='pad-net')), 1)
        self.assertIsNone(first.child('Number_New'))
        self.assertIsNone(first.child('NetNumber'))
        self.assertIsNone(component.child('Number'))
        self.assertFalse(document.complete)

    def test_contradiction_is_detected_before_modifying_input(self):
        decoded = fixture(disagree=True)
        component = decoded.board.one('Components/Component')
        pads = component.one('Pattern/Pads').children()
        with self.assertRaisesRegex(DipError, 'contradicts'):
            assemble_core(decoded)
        self.assertEqual(component['Number'], 41)
        self.assertEqual(component.one('Pattern/Pads').children(), pads)
        self.assertIsNone(decoded.root._document)

    def test_deleted_pad_handles_are_removed_without_reinterpreting_saved_member_keys(self):
        decoded = fixture()
        collection = decoded.board.one('Components/Component/Pattern/Pads')
        deleted = new_pad('deleted')
        deleted['Number_New'] = -1
        deleted.add('NetNumber', -1)
        collection.insert(deleted, 2)
        result = assemble_core(decoded)
        self.assertIsNone(deleted.parent)
        self.assertEqual(len(result.pads), 2)
        self.assertIs(result.document.one('/Board/Nets/Net/Pads/Item')['Pad'], result.pads[41, 5])


if __name__ == '__main__':
    unittest.main()
