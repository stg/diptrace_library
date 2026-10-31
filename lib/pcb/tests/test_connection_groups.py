"""Connectivity is derived from current labels/pairs, not saved group arrays."""
from decimal import Decimal, localcontext
import unittest
from unittest.mock import patch

from lib.common.references import ReferenceError
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.model.connection_groups import groups, ratlines, pad_label_key
from lib.common.footprint_objects import new_pad
from lib.pcb.tests.test_core_assembly import fixture


def design(labels, pairs=(), *, flags=(), saved_groups=None):
    decoded = fixture()
    component = decoded.board.one('Components/Component')
    pads = component.one('Pattern/Pads')
    for pad in pads.children()[1:-1]:
        pad.detach()
    for index, label in enumerate(labels, 1):
        pad = new_pad(label, x=index, index=index)
        # Source identities need not be compact array positions.
        pad['Number_New'] = index*10
        pad.add('NetNumber', -1)
        pad.add('InternalConnection', 999)
        pads.insert(pad, index)
    decoded.board.one('Nets/Net/Pads/Item').detach()
    definitions = component.add('InternalConnection_Records')
    for first, second in pairs:
        definitions.add('pt', first*10, second*10)
    saved = component.add('InternalConnections')
    for index, flag in enumerate(flags):
        group = saved.add('IntCon', index)
        group.add('ConnectAll', flag)
        members = saved_groups[index] if saved_groups is not None else (index*2+1, index*2+2)
        membership = group.add('PadId')
        for number in members:
            membership.add('Item', number*10)
        line = group.add('Ratlines').add('Ratline', 0)
        line.add('X', members[-1]*10)
        line.add('Y', members[0]*10)
    return assemble_core(decoded)


class ConnectionGroupTests(unittest.TestCase):
    def test_electrical_labels_ignore_only_spaces_and_at_signs(self):
        self.assertEqual(pad_label_key(' @A 1@ '), 'A1')
        self.assertNotEqual(pad_label_key('a1'), pad_label_key('A1'))
        self.assertNotEqual(pad_label_key('A\t1'), pad_label_key('A1'))
        result = design(('A1', ' @A 1', 'a1', '', '@ '))
        pads = tuple(result.pads.values())
        self.assertEqual(groups(result.components[41]), ((pads[0], pads[1]), (pads[3], pads[4])))

    def test_explicit_pairs_combine_label_groups_and_can_include_fiducials(self):
        result = design(('1', '1', '2', '2', '1'), ((2, 3),))
        component = result.components[41]
        pads = tuple(result.pads.values())
        pads[4]['PadShape_New'] = 20
        self.assertEqual(groups(component), (pads[:4],))
        component.one('IntConRecords/Item')['Pad2'] = pads[4]
        self.assertEqual(groups(component), ((pads[0], pads[1], pads[4]), (pads[2], pads[3])))

    def test_self_pairs_participate_and_unresolved_pairs_are_explicit_errors(self):
        result = design(('1', '2'), ((1, 1),))
        component = result.components[41]
        self.assertEqual(groups(component), ((result.pads[41, 10],),))
        result.document.remove(component.one('InternalConnections/IntCon'))
        component.one('IntConRecords/Item')['Pad1'] = None
        with self.assertRaises(ReferenceError):
            groups(component)

    def test_views_follow_data_edits_and_reordering_without_a_document_scan(self):
        result = design(('1', '1', '2', '2'))
        component = result.components[41]
        pads = tuple(result.pads.values())
        for policy in component.select('InternalConnections/IntCon'):
            result.document.remove(policy)
        with patch.object(result.document.root, 'walk', side_effect=AssertionError('whole document scan')):
            self.assertEqual(groups(component), ((pads[0], pads[1]), (pads[2], pads[3])))
            pads[0]['StringNumber'] = '2'
            pads[2].move_to(pads[2].parent, 0)
            self.assertEqual(groups(component), ((pads[2], pads[0], pads[3]),))

    def test_ratlines_minimize_distance_without_moving_pads_or_storing_a_cache(self):
        result = design(('1', '1', '1', '1'))
        pads = tuple(result.pads.values())
        for pad, point in zip(pads, ((0, 0), (10, 0), (1, 0), (2, 0))):
            pad['X'], pad['Y'] = point
        before = tuple((pad['X'], pad['Y']) for pad in pads)
        lines = ratlines(pads)
        self.assertEqual(lines, ((pads[0], pads[2]), (pads[2], pads[3]), (pads[3], pads[1])))
        length_squared = sum((a['X']-b['X'])**2 + (a['Y']-b['Y'])**2 for a, b in lines)
        self.assertEqual(length_squared, Decimal(66))
        self.assertEqual(tuple((pad['X'], pad['Y']) for pad in pads), before)
        self.assertEqual(ratlines(pads[:1]), ())
        self.assertEqual(ratlines(()), ())
        with self.assertRaises(ValueError):
            ratlines((pads[0], pads[0]))

    def test_display_tree_is_independent_of_decimal_context_and_handles_coincident_pads(self):
        result = design(('1', '1', '1', '1'))
        pads = tuple(result.pads.values())
        for pad, value in zip(pads, ('0', '1.004', '1.005', '2.009')):
            pad['X'] = Decimal(value)
        expected = ratlines(pads)
        with localcontext() as context:
            context.prec = 2
            self.assertEqual(ratlines(pads), expected)
        for pad in pads:
            pad['X'] = 0
        self.assertEqual(ratlines(pads), tuple((pads[0], pad) for pad in pads[1:]))


if __name__ == '__main__':
    unittest.main()
