"""Generated ratline selectors survive compaction, reorder and absent endpoints."""
import unittest

from lib.common.asc import dumps
from lib.common.model import Element
from lib.pcb.formats.asc.ratline_projection import project_ratlines
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.tests.test_ratlines import source
from lib.pcb.tests.test_rule_projection import current_input


class RatlineProjectionTests(unittest.TestCase):
    def test_first_compacted_pad_has_a_positive_output_selector(self):
        result = assemble_core(source())
        document = result.document
        board = document.one('/Board')
        row = board.one('Ratlines/Ratline')
        before = dumps(document, preserve=False)
        self.assertEqual((row['PadIndex1'], row['PadIndex2']), (0, 1))
        projected = project_ratlines(board.one('Ratlines'))
        self.assertEqual(projected.one('Connection').values, ('Y', 1, 2, 3, 4, 0, 0, 1, 2, 'Y'))
        container = Element('Board')
        container.append(projected)
        current = assemble_core(current_input(board, container)).document.one('/Board/Ratlines/Ratline')
        self.assertEqual((current['PadIndex1'], current['PadIndex2']), (0, 1))
        self.assertTrue(current['Hidden'])
        self.assertEqual((current['X2'], current['Y2']), (3, 4))
        self.assertEqual(dumps(document, preserve=False), before)
        document.references.validate()

    def test_reparented_pad_reordered_components_and_absent_endpoint_are_current(self):
        result = assemble_core(source())
        document = result.document
        row = document.one('/Board/Ratlines/Ratline')
        second = document.copy(result.components[41], fields={'RefDes': 'U2'})
        row['Pad1'].move_to(second.one('Pattern/Pads'))
        second.move_to(second.parent, 0)
        row['Pad2'] = None
        row['Hidden'] = False
        projected = project_ratlines(row.parent).one('Connection')
        self.assertEqual(projected.values[5:], (0, -1, 3, -1, 'N'))
        self.assertIs(row['Component1'], second)
        self.assertIsNone(row['Pad2'])
        document.references.validate()


if __name__ == '__main__':
    unittest.main()
