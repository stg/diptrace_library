"""Binary pair sections reopen into the same editable routing relationships."""
from dataclasses import replace
from decimal import Decimal
import unittest

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport, import_diagnostics
from lib.common.model import Element
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.formats.dip.differential_pairs import read_initial_pairs, read_routing_extensions
from lib.pcb.formats.dip.meanders import read_meanders
from lib.pcb.formats.dip.nets import read_base_nets
from lib.pcb.formats.dip.read import Reader
from lib.pcb.formats.dip.results import read_initial_results
from lib.pcb.formats.dip.writer import Writer
from lib.pcb.formats.dip.write_nets import write_base_nets
from lib.pcb.formats.dip.write_pairs import write_initial_pairs, write_routing_extensions, write_meanders
from lib.pcb.formats.dip.write_results import write_initial_results
from lib.pcb.formats.errors import PcbError
from lib.pcb.formats.output_indices import OutputIndices
from lib.pcb.model.objects import new_pair, new_net_class
from lib.pcb.tests.test_pair_projection import design, signature, syntax
from lib.pcb.tests.test_net_projection import signature as net_signature


def sections(document, *, report=None):
    """A bounded section stream, deliberately not a complete DIP file."""
    board, writer = document.one('/Board'), Writer(report=report)
    writer.header()
    write_base_nets(writer, board)
    write_initial_results(writer, board)
    write_initial_pairs(writer, board)
    write_routing_extensions(writer, board)
    write_meanders(writer, board)
    return bytes(writer.buffer)


def read_sections(document, *, report=None):
    data = sections(document, report=report)
    reader, board = Reader(data+b'\0'), Element('Board')
    classes = board.add('NetClasses')
    for current in OutputIndices(document.one('/Board')).classes:
        properties = classes.add('NetClass').add('LayProperties')
        for _ in current.select('LayProperties/LayProperty'):
            properties.add('LayProperty')
    board.add('DRC')
    nets = read_base_nets(reader, board)
    read_initial_results(reader, board)
    read_initial_pairs(reader, board)
    separate = read_routing_extensions(reader, board)
    read_meanders(reader, board)
    if reader.pos != len(data):
        raise AssertionError('differential section boundary differs')
    return board, data, nets, separate


def reopen(document, *, report=None, source=None):
    raw, _, nets, separate = read_sections(document, report=report)
    prepared = prepare_core(dumps(syntax(document, report=ConversionReport()) if source is None else source,
                                  preserve=False))
    # Teardrops are a later, independent binary section. Supply their prepared
    # fixtures while isolating the earlier net/pair/result sections here.
    for source_net, raw_net in zip(prepared.board.select('Nets/Net'), raw.select('Nets/Net')):
        if (teardrops := source_net.child('Teardrops')) is not None:
            teardrops.move_to(raw_net)
    for name in ('Nets', 'DifferentialPairs', 'DesignErrors', 'RemovedDifferentialPairs', 'LastDRC'):
        if (previous := prepared.board.child(name)) is not None:
            previous.detach()
        raw.one(name).move_to(prepared.board)
    prepared = replace(prepared, upgrades=replace(prepared.upgrades, nets=nets, separate_traces=separate))
    return assemble_graphics(prepared).document


def with_rules(document):
    board = document.one('/Board')
    for kind in ('DRC', 'LastDRC'):
        if board.child(kind) is None:
            board.add(kind)
    return document


class DipPairOutputTests(unittest.TestCase):
    def test_current_geometry_and_relationships_reopen_without_source_mutation(self):
        document = with_rules(design())
        pair = document.one('/Board/DifferentialPairs/DifferentialPair')
        pair['RouteMode'], pair['AutoPadPoints'], pair['TraceColor'] = 3, False, 0x123456
        point = pair.one('Segments/Segment/CenterPoints/CenterPoint[1]/PosPoints/PosPoint')
        point['Meander'], point['MeanderAngle'], point['Arc'], point['Necked'] = 2, Decimal('.37'), True, True
        separate = pair.one('PosSeparateTraces/PosTrace/Points/Point')
        separate['Meander'], separate['MeanderAngle'], separate['PairNecked'] = 4, Decimal('1.125'), True
        net = document.one('/Board/Nets/Net[1]')
        net['MeanderGap'] = Decimal('2.75')
        net.one('Traces/Trace/Points/Point[1]')['PhaseFwd'] = Decimal('5.125')
        before, expected, nets = dumps(document, preserve=False), signature(document), net_signature(document)
        rebuilt = reopen(document)
        self.assertEqual(signature(rebuilt), expected)
        self.assertEqual(net_signature(rebuilt), nets)
        self.assertEqual(signature(reopen(rebuilt)), expected)
        self.assertEqual(sections(rebuilt), sections(document))
        self.assertEqual(dumps(document, preserve=False), before)
        rebuilt.references.validate()

    def test_reordering_pads_centers_and_trace_points_regenerates_all_selectors(self):
        document = with_rules(design())
        pair = document.one('/Board/DifferentialPairs/DifferentialPair')
        pair.one('PadPoints/PadPoint')['PosPad'].move_to(document.one('/Board/Components/Component/Pattern/Pads'))
        centers = pair.one('Segments/Segment/CenterPoints')
        centers.one('CenterPoint[2]').move_to(centers, 0)
        trace = pair.one('Segments/Segment')['PosTrace']
        trace.one('Points/Point[2]').move_to(trace.one('Points'), 0)
        raw, _, _, _ = read_sections(document)
        saved = raw.one('DifferentialPairs/DifferentialPair')
        self.assertEqual(saved.one('PadPoints/PadPoint')['PosPad'], 2)
        center = saved.one('Segments/Segment/CenterPoints/CenterPoint[1]')
        self.assertEqual((center['Orientation'], center['PosTrace_StartPoint'], center['PosTrace_EndPoint']), (0, 1, 0))
        self.assertEqual(signature(reopen(document)), signature(document))
        self.assertEqual(net_signature(reopen(document)), net_signature(document))

    def test_unresolved_current_range_remains_explicit_and_reports_a_warning(self):
        source = syntax(design())
        source.one('/Board/DifferentialPairs/DifferentialPair/Segments/Segment/CenterPoints/CenterPoint[1]/PosLine_EndPoint').set_values(100)
        reader = import_diagnostics('asc')(lambda text: assemble_graphics(prepare_core(text)).document)
        document = with_rules(reader(dumps(source, preserve=False), report=ConversionReport()))
        report = ConversionReport()
        rebuilt = reopen(document, report=report)
        self.assertEqual({notice.rule for notice in report.warnings}, {'unresolved-pair-range'})
        center = rebuilt.one('/Board/DifferentialPairs/DifferentialPair/Segments/Segment/CenterPoints/CenterPoint[1]')
        self.assertEqual(center['UnresolvedPosEndPointIndex'], 100)

    def test_class_phase_and_neck_records_follow_the_selected_default_class_order(self):
        document = with_rules(design())
        board = document.one('/Board')
        for index in (1, 2):
            net_class = board.one('NetClasses').append(new_net_class('Class'+str(index)))
            net_class['AllLayers'], net_class['Phase'], net_class['Phase_ErrorLength'] = True, index*11, index*3
            row = net_class.add('LayProperties').add('LayProperty')
            row['Neck_Width'], row['Neck_DifClearance'], row['Neck_MaxLength'] = index, index*2, index*4
        first, second = board.select('NetClasses/NetClass')
        board['DefaultClass'] = second
        board.one('DifferentialPairs/DifferentialPair')['Class'] = first
        raw, _, _, _ = read_sections(document)
        self.assertEqual([row['Phase'] for row in raw.select('NetClasses/NetClass')], [22, 11])
        self.assertEqual([row['Neck_Width'] for row in raw.select('NetClasses/NetClass/LayProperties/LayProperty')], [2, 1])
        self.assertEqual(raw.one('DifferentialPairs/DifferentialPair')['NetClass'], 1)

    def test_unassigned_pair_and_unknown_or_restorable_content_fail_without_mutation(self):
        for kind in ('net', 'unknown', 'removed'):
            document = with_rules(design())
            pair = document.one('/Board/DifferentialPairs/DifferentialPair')
            if kind == 'net':
                pair.parent.append(new_pair('Incomplete'))
            elif kind == 'unknown':
                pair.add('Unmapped', 7)
            else:
                document.one('/Board').add('RemovedDifferentialPairs').add('RemovedDifferentialPair')
            before = dumps(document, preserve=False)
            with self.subTest(kind=kind), self.assertRaises(PcbError):
                sections(document)
            self.assertEqual(dumps(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
