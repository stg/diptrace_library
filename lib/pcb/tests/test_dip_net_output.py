"""Binary routing sections use current identities and generated compatibility."""
from decimal import Decimal
import unittest

from lib.common.asc import dumps, loads
from lib.common.binary import BinaryReader
from lib.common.model import Element
from lib.pcb.formats.capabilities import DIP
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.formats.dip.differential_pairs import (read_initial_pairs,
    read_routing_extensions, _separate_traces)
from lib.pcb.formats.dip.nets import read_base_nets, read_connections
from lib.pcb.formats.dip.read import Reader
from lib.pcb.formats.dip.writer import Writer
from lib.pcb.formats.dip.write_nets import (write_connections, write_base_nets,
    write_trace, write_point_pair_extensions, write_trace_relationships)
from lib.pcb.formats.errors import PcbError
from lib.pcb.model.objects import new_point, new_trace
from lib.pcb.tests.test_net_projection import design
from lib.pcb.tests.test_asc_differential_pairs import design as pair_source
from lib.pcb.tests.test_component_projection import design as component_design, project_input


def sections(document):
    board = document.one('/Board')
    writer = Writer()
    writer.header()
    write_connections(writer, board)
    write_base_nets(writer, board)
    # Empty pair/removed-pair and last-rule envelopes isolate the ordinary
    # routing extensions. This stream is a section fixture, not a DIP file.
    writer.integer(0)
    write_point_pair_extensions(writer, board)
    writer.integer(0)
    writer.text('')
    for _ in range(8):
        writer.boolean(False)
    writer.integer(0)
    writer.integer(0)
    write_trace_relationships(writer, board)
    return bytes(writer.buffer)


def read_sections(document):
    data = sections(document)
    reader, board = Reader(data+b'\0'), Element('Board')
    read_connections(reader, board)
    upgrades = read_base_nets(reader, board)
    read_initial_pairs(reader, board)
    read_routing_extensions(reader, board)
    if reader.pos != len(data):
        raise AssertionError('routing section boundary differs')
    return board, data, upgrades


class DipNetOutputTests(unittest.TestCase):
    def test_active_selection_writes_point_before_line_in_every_output_schema(self):
        document = design()
        board = document.one('/Board')
        net = board.one('Nets/Net')
        net['ActivePoint'], net['ActiveLine'] = 1, 0
        before = dumps(document, preserve=False)
        for version in DIP.write_versions:
            with self.subTest(version=version):
                writer = Writer(version)
                writer.header()
                start = len(writer.buffer)
                write_base_nets(writer, board)
                # Read primitives directly, without the DIP net-field mapping.
                wire = BinaryReader(bytes(writer.buffer), offset=start)
                self.assertEqual(wire.integer(), 1)
                self.assertEqual((wire.boolean(), wire.boolean()), (True, False))
                self.assertEqual((wire.integer(), wire.integer(), wire.integer()), (1, 0, -1))
        self.assertEqual(dumps(document, preserve=False), before)

    def test_current_membership_endpoint_and_point_order_determine_saved_indices(self):
        document = design()
        net = document.one('/Board/Nets/Net')
        first = net.one('Traces/Trace')
        pad = first['Target1']
        pad.move_to(pad.parent)
        target = first.one('Points/Point[2]')
        other = net.one('Traces').append(new_trace())
        other.one('Points').append(new_point(x=8, y=9))
        other['Target1'] = target
        target.move_to(target.parent, 0)
        first.move_to(first.parent)
        before = dumps(document, preserve=False)
        rebuilt, data, _ = read_sections(document)
        traces = rebuilt.select('Nets/Net/Traces/Trace')
        self.assertEqual(tuple(traces[0][name] for name in ('Connected1','Object1','SubObject1','Point1')),
                         (1, 0, 1, 0))
        self.assertEqual(traces[0]['Connected2'], -1)
        self.assertEqual(tuple(traces[1][name] for name in ('Connected1','Object1','SubObject1','Point1')),
                         (0, 0, 2, -1))
        self.assertEqual([row.values for row in rebuilt.select('Nets/Net/Pads/Item')], [(0, 2), (0, 1)])
        self.assertEqual(traces[1].one('Points/Point[1]')['X'], 3)
        self.assertEqual(sections(document), data)
        self.assertEqual(dumps(document, preserve=False), before)
        document.references.validate()

    def test_via_snapshots_and_direction_are_generated_from_current_style_and_geometry(self):
        document = design()
        board = document.one('/Board')
        style = board.one('ViaStyles/ViaStyle')
        point = board.one('Nets/Net/Traces/Trace/Points/Point[2]')
        point['Via'] = style
        style['Size'], style['HoleSize'] = Decimal('3.5'), Decimal('1.5')
        style['Span'] = (board.one('Layers/Layer[1]'), board.one('Layers/Layer[2]'))
        rebuilt, data, _ = read_sections(document)
        net = rebuilt.one('Nets/Net')
        compatibility = BinaryReader(data, offset=net.one('Name').source.end)
        self.assertEqual((compatibility.number(), compatibility.number(), compatibility.boolean()), (Decimal('3.5'), 1, False))
        current = net.one('Traces/Trace/Points/Point[2]')
        wire = BinaryReader(data, offset=current.source.start+11)
        self.assertEqual((wire.integer(), wire.number(), wire.number(), wire.boolean()), (3, Decimal('.75'), Decimal('3.5'), False))
        self.assertEqual((wire.integer(), wire.boolean(), wire.integer(), wire.number(), wire.integer(), wire.integer()),
                         (0, False, 0, Decimal('1.5'), 0, 1))
        self.assertIsNone(point.child('Direction'))
        self.assertIsNone(point.child('ViaSize'))
        self.assertEqual((point['X'], point['Y']), (3, 4))

    def test_phase_absence_and_current_endpoint_modes_are_explicit_in_later_sections(self):
        document = design()
        point = document.one('/Board/Nets/Net/Traces/Trace/Points/Point[2]')
        point['PhaseFwd'], point['PairNecked'] = Decimal('12.5'), True
        rebuilt, _, _ = read_sections(document)
        current = rebuilt.one('Nets/Net/Traces/Trace/Points/Point[2]')
        self.assertEqual((current['PhaseFwd'], current['PhaseBack']), (Decimal('12.5'), -100000))
        self.assertTrue(current['PairNecked'])
        self.assertEqual(current['PairSubPoint'], -1)
        self.assertIsNone(point['PhaseBack'])

    def test_guide_geometry_and_optional_pad_endpoints_keep_their_own_state(self):
        document = design()
        board = document.one('/Board')
        guide = board.add('Ratlines').add('Ratline')
        guide['Enabled'], guide['Hidden'] = False, True
        for name, value in dict(X1=1, Y1=2, X2=3, Y2=4).items():
            guide[name] = value
        first, second = document.select('/Board/Components/Component/Pattern/Pads/Pad')
        guide['Pad1'], guide['Pad2'] = first, second
        first.move_to(first.parent)
        rebuilt, _, _ = read_sections(document)
        current = rebuilt.one('Connections/Connection')
        self.assertEqual(tuple(current[name] for name in ('Enabled','Hidden','X1','Y1','X2','Y2','Comp1','Comp2','Pad1','Pad2')),
                         (False, True, 1, 2, 3, 4, 0, 0, 2, 1))
        guide['Pad2'] = None
        rebuilt, _, _ = read_sections(document)
        current = rebuilt.one('Connections/Connection')
        self.assertEqual((current['Comp2'], current['Pad2']), (-1, -1))

    def test_separate_trace_retains_full_endpoint_modes_and_necked_point_state(self):
        source = loads(pair_source())
        context = project_input(component_design())
        for name in ('Layers', 'ViaStyles'):
            context.one('/Board/'+name).move_to(source.one('/Board'))
        document = assemble_graphics(prepare_core(dumps(source, preserve=False))).document
        trace = document.one('/Board/DifferentialPairs/DifferentialPair/PosSeparateTraces/PosTrace')
        before = dumps(document, preserve=False)
        writer = Writer()
        writer.header()
        writer.integer(1)
        write_trace(writer, trace, separate=True)
        reader, pair = Reader(bytes(writer.buffer)+b'\0'), Element('DifferentialPair')
        upgrades = _separate_traces(reader, pair, 'Pos')
        actual = pair.one('PosSeparateTraces/PosTrace')
        self.assertEqual(reader.pos, len(writer.buffer))
        self.assertEqual((actual['Connected1'], actual['Connected2']), (5, 0))
        self.assertEqual(actual['TraceId'], 0)
        self.assertEqual(actual.one('Points/Point')['Jumper'], 2)
        self.assertFalse(actual.one('Points/Point')['Arc'])
        self.assertEqual(upgrades[0].previous_number, trace['Id'])
        self.assertEqual(dumps(document, preserve=False), before)

    def test_unmapped_routing_content_is_rejected_without_mutation(self):
        document = design()
        document.one('/Board/Nets/Net/Traces/Trace/Points/Point[1]').add('Unmapped', 5)
        before = dumps(document, preserve=False)
        with self.assertRaises(PcbError):
            sections(document)
        self.assertEqual(dumps(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
