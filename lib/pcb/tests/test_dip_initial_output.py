"""Current board facts generate the binary prefix without source replay.

These tests deliberately stop before component data: the section writer is not
a complete DIP adapter. Existing input fixtures exercise hierarchy, identities
and rule modernization independently of this output implementation.
"""
from decimal import Decimal
from pathlib import Path
import unittest
from unittest.mock import patch

from lib.common.asc import dumps
from lib.common.model import Document
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.assembly.board_rules import assemble_rules
from lib.pcb.formats.dip.binary import UnsupportedVersionError
from lib.pcb.formats.dip.preamble import read_initial_sections
from lib.pcb.formats.dip.read import Reader
from lib.pcb.formats.dip.write_initial import write_initial_sections
from lib.pcb.formats.dip.writer import Writer
from lib.pcb.formats.errors import PcbError
from lib.pcb.model.objects import new_document
from lib.pcb.tests.test_asc_rules import fixture as rule_fixture
from lib.pcb.tests.test_global_projection import design as hierarchy_design


def prefix(document):
    writer = Writer()
    write_initial_sections(writer, document)
    return bytes(writer.buffer)


def read_prefix(document):
    data = prefix(document)
    # Count validation requires space for the following component records. The
    # sentinel stands for unimplemented later sections and is never consumed.
    tail = b'\0'*max(1, len(document.select('/Board/Components/Component')))
    reader, result = Reader(data+tail), Document()
    state = read_initial_sections(reader, result.root)
    if reader.pos != len(data):
        raise AssertionError('prefix reader did not stop at the section boundary')
    return result, state


class DipInitialOutputTests(unittest.TestCase):
    def test_header_and_new_board_defaults_have_no_companion_dependency(self):
        document = new_document()
        before = dumps(document, preserve=False)
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('companion read')):
            raw = prefix(document)
            result, state = read_prefix(document)
        self.assertEqual(raw[:11], bytes.fromhex('07 4454424f415244 0f427e'))
        self.assertEqual(result.one('/Scale').values, (100,))
        self.assertEqual([layer.values for layer in result.select('/Board/Layers/Layer')],
                         [('Top',), ('Bottom',)])
        self.assertEqual((state.component_count, state.legacy_picture_count), (0, 0))
        self.assertEqual(result.one('/Board/CompFontSize').values, (2,))
        self.assertEqual(result.one('/Board/PanelX').values, (1,))
        self.assertEqual(prefix(document), raw)
        self.assertEqual(dumps(document, preserve=False), before)

    def test_hierarchy_keys_remain_persistent_while_order_and_labels_change(self):
        document = hierarchy_design()
        board = document.one('/Board')
        sheet = board.one('HierarchySheets/HSheet[1]')
        sheet['Name'], sheet['Number'] = 'Renamed sheet Ω', 44
        block = sheet.one('UpdateIds/UId')
        block['Id'], block['Name'] = 104, 'Renamed instance'
        sheet.move_to(sheet.parent)
        before = dumps(document, preserve=False)
        result, state = read_prefix(document)
        restored = result.one('/Board/HierarchySheets/HSheet[2]')
        self.assertEqual(restored.values, ('Renamed sheet Ω', 44))
        self.assertEqual(restored.one('UpdateIds/UId').values, (104, 'Renamed instance'))
        self.assertEqual(result.one('/Board/OriginX').values, (12,))
        self.assertEqual(result.one('/Board/UserField1').values, ('Order',))
        self.assertEqual(state.component_count, 1)
        self.assertEqual(dumps(document, preserve=False), before)
        document.references.validate()

    def test_rule_output_regenerates_positions_and_symmetric_clearance_rows(self):
        document = assemble_rules(prepare_core(rule_fixture())).document
        board = document.one('/Board')
        top, plane, bottom = board.select('Layers/Layer')
        bottom.move_to(bottom.parent, 1)
        default, signal = board.select('NetClasses/NetClass')
        signal.move_to(signal.parent, 0)
        # Default-class identity controls the wire slot, not collection order.
        before = dumps(document, preserve=False)
        result, _ = read_prefix(document)
        layers = result.select('/Board/Layers/Layer')
        self.assertEqual([row.values[0] for row in layers], ['Top', 'Bottom', 'Plane'])
        self.assertEqual([row.one('Number').values[0] for row in layers], [0, 1, 2])
        self.assertEqual(result.one('/Board/ViaStyles/ViaStyle[2]').values,
                         ('Blind', False, 1, Decimal('.5'), 0, 2))
        classes = result.select('/Board/NetClasses/NetClass')
        self.assertEqual([row.values[0] for row in classes], ['Default', 'Signal'])
        first = classes[0].one('LayProperties/LayProperty')
        self.assertEqual((first.one('MinWidth').values[0], first.one('MaxWidth').values[0]),
                         (Decimal('.03'), 300))
        self.assertEqual(first.one('ClearDetails/pt[4]').values, (-1, -1, -1, 13, 14))
        self.assertEqual([row.one('Width').values[0] for row in classes[1].select('LayProperties/LayProperty')],
                         [1, 3, 2])
        self.assertEqual([row.values[0] for row in classes[1].select('RouteLayers/Item')],
                         [True, True, False])
        matrix = result.one('/Board/ClassClearances')
        expected = [Decimal('.1'), Decimal('.3'), Decimal('.2')]
        for row, column in ((1, 2), (2, 1)):
            self.assertEqual([item.values[0] for item in matrix.select(f'Row[{row}]/Cell[{column}]/Values/Item')],
                             expected)
        self.assertEqual(dumps(document, preserve=False), before)
        document.references.validate()

    def test_missing_or_unknown_data_is_rejected_without_changing_the_source(self):
        for operation in ('unmapped', 'incomplete-layer-rules'):
            document = assemble_rules(prepare_core(rule_fixture())).document
            if operation == 'unmapped':
                document.one('/Board/Layers/Layer[1]').add('Unmapped', 12)
            else:
                row = document.one('/Board/NetClasses/NetClass[2]/LayProperties/LayProperty[1]')
                document.remove(row)
            before = dumps(document, preserve=False)
            with self.subTest(operation=operation), self.assertRaises(PcbError):
                prefix(document)
            self.assertEqual(dumps(document, preserve=False), before)

    def test_generated_length_interval_accepts_independent_numeric_types(self):
        for fixed in (12, 12.0, Decimal('12')):
            for delta in (3, 3.0, Decimal('3')):
                with self.subTest(fixed=type(fixed).__name__, delta=type(delta).__name__):
                    document = assemble_rules(prepare_core(rule_fixture())).document
                    net_class = document.one('/Board/NetClasses/NetClass[2]')
                    net_class['FixedLength'], net_class['LengthDelta'] = fixed, delta
                    before = dumps(document, preserve=False)
                    restored, _ = read_prefix(document)
                    actual = restored.one('/Board/NetClasses/NetClass[2]')
                    self.assertEqual(actual.one('MinLength').values, (Decimal('10.5'),))
                    self.assertEqual(actual.one('MaxLength').values, (Decimal('13.5'),))
                    self.assertEqual(dumps(document, preserve=False), before)

    def test_only_the_implemented_section_revisions_are_accepted(self):
        for version in (31, 53, 63, True, 62.0):
            with self.subTest(version=version), self.assertRaises(UnsupportedVersionError):
                Writer(version)

    def test_sparse_class_matrix_stops_at_its_last_current_pair(self):
        document = assemble_rules(prepare_core(rule_fixture())).document
        cells = document.select('/Board/ClassClearances/Cell')
        for cell in cells[1:]:
            document.remove(cell)
        result, _ = read_prefix(document)
        self.assertEqual(len(result.select('/Board/NetClasses/NetClass')), 2)
        self.assertEqual(len(result.select('/Board/ClassClearances/Row')), 1)
        self.assertEqual(len(result.select('/Board/ClassClearances/Row/Cell')), 1)


if __name__ == '__main__':
    unittest.main()
