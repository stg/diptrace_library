"""Deleted electrical slots do not become current identities or geometry."""
from dataclasses import replace
import unittest

from lib.common.conversion import ConversionReport, import_diagnostics
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.formats.assembly.routing_inputs import NetInput, TraceInput
from lib.pcb.formats.dip.decode import decode
from lib.pcb.formats.dip.write import encode
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_core_assembly import fixture
from lib.pcb.tests.test_dip_output import configured_document, reopen, assemble_preserving_colors
from lib.pcb.tests.test_cache_projection import signature


@import_diagnostics('asc')
def read_core(inputs):
    return assemble_core(inputs).document


class InactiveElectricalTests(unittest.TestCase):
    def test_deleted_slots_can_repeat_keys_without_becoming_ambiguous(self):
        inputs = fixture()
        board = inputs.board
        deleted_part = board.one('Components').append(board.one('Components/Component').clone())
        deleted_part.one('Enabled').set_values(False)
        for pad in deleted_part.select('Pattern/Pads/Pad'):
            pad.one('NetNumber').set_values(9999)
        deleted_net = board.one('Nets').append(board.one('Nets/Net').clone())
        deleted_net.one('Enabled').set_values(False)
        deleted_net.one('Pads/Item').set_values(9999, 9999)
        report = ConversionReport()
        document = read_core(inputs, report=report)
        self.assertEqual(len(document.select('/Board/Components/Component')), 1)
        self.assertEqual(len(document.select('/Board/Nets/Net')), 1)
        self.assertEqual(len(document.select('/Board/Components/Component/Pattern/Pads/Pad')), 2)
        self.assertIsNone(deleted_part.parent)
        self.assertIsNone(deleted_net.parent)
        self.assertEqual(len([notice for notice in report.infos if notice.rule == 'inactive-electrical-records']), 1)
        document.references.validate()

    def test_all_deleted_records_produce_an_empty_current_electrical_model(self):
        inputs = fixture()
        for node in (*inputs.board.select('Components/Component'), *inputs.board.select('Nets/Net')):
            node.one('Enabled').set_values(False)
        result = assemble_core(inputs)
        self.assertEqual((result.components, result.nets, result.pads), ({}, {}, {}))
        self.assertEqual(result.document.select('/Board/Components/Component'), [])
        self.assertEqual(result.document.select('/Board/Nets/Net'), [])
        result.document.references.validate()

    def test_active_contradictions_still_fail_before_deleted_slots_are_removed(self):
        inputs = fixture(disagree=True)
        deleted = inputs.board.one('Components').append(inputs.board.one('Components/Component').clone())
        deleted.one('Enabled').set_values(False)
        with self.assertRaisesRegex(PcbError, 'contradicts'):
            assemble_core(inputs)
        self.assertIs(deleted.parent, inputs.board.one('Components'))
        self.assertIsNone(inputs.root._document)

    def test_an_ambiguous_active_reference_remains_an_error(self):
        inputs = fixture()
        inputs.board.one('Components').append(inputs.board.one('Components/Component').clone())
        with self.assertRaisesRegex(PcbError, 'ambiguous saved net pad reference'):
            assemble_core(inputs)

    def test_inactive_net_routes_are_excluded_from_full_relationship_binding(self):
        data = encode(configured_document(), report=ConversionReport())
        expected = signature(reopen(data, report=ConversionReport()).root)
        inputs = decode(data)
        board = inputs.board
        deleted_part = board.one('Components').append(board.one('Components/Component').clone())
        deleted_part.one('Enabled').set_values(False)
        deleted_net = board.one('Nets').append(board.one('Nets/Net').clone())
        deleted_net.one('Enabled').set_values(False)
        routes = []
        for previous, trace in zip(inputs.upgrades.nets[0].traces, deleted_net.select('Traces/Trace')):
            trace.one('Object1').set_values(999999)
            routes.append(TraceInput(trace, previous.previous_number, ()))
        upgrades = replace(inputs.upgrades, nets=(*inputs.upgrades.nets, NetInput(deleted_net, tuple(routes))))
        inputs = replace(inputs, upgrades=upgrades)
        current = assemble_preserving_colors(inputs)
        self.assertEqual(signature(current.root), expected)
        self.assertEqual(encode(current, report=ConversionReport()), data)
        current.references.validate()


if __name__ == '__main__':
    unittest.main()
