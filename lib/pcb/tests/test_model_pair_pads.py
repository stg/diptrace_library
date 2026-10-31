"""Paired pad identities remain coherent under ordinary model data edits."""
import unittest

from lib.common.model import Element
from lib.common.references import Property, ReferenceError
from lib.pcb.model import routing_records
from lib.pcb.model.objects import new_document, new_component, new_pad, new_net, new_pair


def design():
    document = new_document()
    board = document.one('/Board')
    positive, negative = (board.one('Nets').append(new_net(name)) for name in ('Positive', 'Negative'))
    first, second = (board.one('Components').append(new_component('Device', name)) for name in ('R1', 'R2'))
    pos_pad = first.one('Pattern/Pads').append(new_pad('1'))
    neg_pad = second.one('Pattern/Pads').append(new_pad('1'))
    pos_pad['Net'], neg_pad['Net'] = positive, negative
    pairs = board.add('DifferentialPairs').bind_schema(routing_records.COLLECTIONS['DifferentialPairs'])
    pair = pairs.append(new_pair('Pair'))
    pair['PosNet'], pair['NegNet'] = positive, negative
    row = pair.one('PadPoints').append(Element('PadPoint').bind_schema(routing_records.PAIRED_PAD))
    row['PosPad'], row['NegPad'] = pos_pad, neg_pad
    return document, pair, row, pos_pad, neg_pad


class PairedPadModelTests(unittest.TestCase):
    def test_live_index_projections_follow_component_pad_and_row_order(self):
        document, pair, row, positive, _ = design()
        probe = document.root.add('Probe', -1, -1, -1)
        document.references.bind(probe, row,
            *(Property(probe, name, argument=index) for index, name in
              enumerate(('PosComponentIndex', 'PosPadIndex', 'Id'))), role='probe')
        component = positive.parent.parent.parent
        self.assertEqual(probe.values, (0, 0, 0))
        component.move_to(component.parent)
        positive.parent.append(new_pad('2'))
        positive.move_to(positive.parent)
        pair.one('PadPoints').append(Element('PadPoint').bind_schema(routing_records.PAIRED_PAD))
        row.move_to(row.parent)
        self.assertEqual(probe.values, (1, 1, 1))
        self.assertIs(row['PosPad'], positive)
        document.validate()

    def test_pad_and_net_retargeting_is_atomic_and_explicit_disconnection_is_allowed(self):
        document, pair, row, positive, negative = design()
        net = pair['PosNet']
        with self.assertRaisesRegex(ReferenceError, 'corresponding pair net'):
            row['PosPad'] = negative
        with self.assertRaisesRegex(ReferenceError, 'paired pad'):
            positive['Net'] = negative['Net']
        with self.assertRaisesRegex(ReferenceError, 'paired pad'):
            pair['PosNet'] = negative['Net']
        self.assertIs(row['PosPad'], positive)
        self.assertIs(positive['Net'], net)
        self.assertIs(pair['PosNet'], net)
        row['PosPad'] = None
        pair['PosNet'] = negative['Net']
        self.assertEqual(row['PosPadIndex'], -1)
        document.validate()

    def test_moving_between_incompatible_pairs_rejects_without_detaching(self):
        document, pair, row, positive, negative = design()
        other = pair.parent.append(new_pair('Reversed'))
        other['PosNet'], other['NegNet'] = negative['Net'], positive['Net']
        with self.assertRaisesRegex(ReferenceError, 'corresponding pair net'):
            row.move_to(other.one('PadPoints'))
        self.assertIs(row.parent, pair.one('PadPoints'))
        self.assertIs(row['PosPad'], positive)
        document.validate()

    def test_referenced_pads_cannot_be_removed_and_document_clone_keeps_independent_links(self):
        document, pair, row, positive, _ = design()
        with self.assertRaises(ReferenceError):
            document.remove(positive)
        copied = document.clone()
        new_row = copied.one('/Board/DifferentialPairs/DifferentialPair/PadPoints/PadPoint')
        self.assertIsNot(new_row['PosPad'], positive)
        self.assertIs(new_row['PosPad']._owner(), copied)
        new_row['PosPad'] = None
        self.assertIs(row['PosPad'], positive)
        copied.validate()
        document.validate()


if __name__ == '__main__':
    unittest.main()
