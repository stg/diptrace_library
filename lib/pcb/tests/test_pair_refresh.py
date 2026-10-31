"""Automatic paired-pad data is modernized before routing references bind."""
from dataclasses import replace
import unittest
import xml.etree.ElementTree as ET

from lib.common.asc import loads as asc_loads, dumps as asc_dumps
from lib.common.binary import BinaryWriter
from lib.common.conversion import ConversionReport, import_diagnostics
from lib.pcb.formats import io
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.formats.assembly.routing import assemble_routing
from lib.pcb.formats.assembly.pair_matching import PadLocation, infer_members
from lib.pcb.formats.dip.decode import decode
from lib.pcb.tests.test_dipxml_pairs import source
from lib.pcb.tests.test_xml_routing_output import with_component_library


PAIR = '/Board/DifferentialPairs/DifferentialPair'


def automatic_source():
    root = ET.fromstring(with_component_library(source()))
    root.find('Board/DifferentialPairs/DifferentialPair').set('AutoPadPoints', 'Y')
    return root


def control():
    return io.parse(ET.tostring(automatic_source()), report=ConversionReport())


def without_members(format):
    if format == 'dipxml':
        root = automatic_source()
        root.find('Board/DifferentialPairs/DifferentialPair/PadPoints').clear()
        return ET.tostring(root)
    document = control()
    data = io.serialize(document, format=format, report=ConversionReport())
    if format == 'asc':
        syntax = asc_loads(data.decode('cp1252'))
        for row in tuple(syntax.one(PAIR+'/PadPoints').children()):
            row.detach()
        syntax.one(PAIR+'/PadPoints').set_values(0)
        return asc_dumps(syntax, preserve=False)
    decoded = decode(data)
    rows = decoded.board.select('DifferentialPairs/DifferentialPair/PadPoints/PadPoint')
    start, end = rows[0].one('PosComp').source.start, rows[-1].one('NegPad').source.end
    zero = BinaryWriter()
    zero.integer(0)
    # Change only the count and its rows in a generated portable binary fixture.
    return data[:start-len(zero.buffer)] + bytes(zero.buffer) + data[end:]


class PairRefreshTests(unittest.TestCase):
    def test_every_input_format_rebuilds_members_before_binding_segment_ends(self):
        for format in ('dip', 'asc', 'dipxml'):
            with self.subTest(format=format):
                report = ConversionReport()
                document = io.parse(without_members(format), format=format, report=report)
                pair = document.one(PAIR)
                row = pair.one('PadPoints/PadPoint')
                segment = pair.one('Segments/Segment')
                self.assertIs(segment['Start'], row)
                self.assertIs(segment['End'], row)
                self.assertIs(row['PosPad']['Net'], pair['PosNet'])
                self.assertIs(row['NegPad']['Net'], pair['NegNet'])
                self.assertTrue(any(n.rule == 'automatic-pair-members' for n in report.infos))
                for target in ('dip', 'asc', 'dipxml'):
                    again_report = ConversionReport()
                    again = io.parse(io.serialize(document, format=target, report=ConversionReport()),
                                     format=target, report=again_report)
                    again.references.validate()
                    self.assertEqual(len(again.select(PAIR+'/PadPoints/PadPoint')), 1)
                    self.assertFalse(any(n.rule == 'automatic-pair-members' for n in again_report.notices))

    def test_schema_policy_refreshes_a_populated_pair_and_preserves_its_endpoint_identity(self):
        data = io.serialize(control(), format='dip', version=62, report=ConversionReport())
        decoded = decode(data)
        core = assemble_core(decoded)
        row = decoded.board.one('DifferentialPairs/DifferentialPair/PadPoints/PadPoint')
        first, second = row.one('PosPad'), row.one('NegPad')
        a, b = first.values[0], second.values[0]
        first.set_values(b)
        second.set_values(a)
        # Isolate the older revision's routing policy after core geometry has
        # already been prepared; this is not a synthetic full schema-40 file.
        forced = replace(decoded, header=replace(decoded.header, version=40))
        operation = import_diagnostics('dip')(lambda: assemble_routing(forced, core).document)
        document = operation(report=ConversionReport())
        pair = document.one(PAIR)
        self.assertIs(pair.one('PadPoints/PadPoint'), row)
        self.assertIs(row['PosPad']['Net'], pair['PosNet'])
        self.assertIs(pair.one('Segments/Segment')['Start'], row)

    def test_a_manual_empty_pair_stays_manual_and_empty(self):
        root = automatic_source()
        pair = root.find('Board/DifferentialPairs/DifferentialPair')
        pair.set('AutoPadPoints', 'N')
        for name in ('PadPoints', 'Segments', 'PosSeparateTraces', 'NegSeparateTraces'):
            pair.find(name).clear()
        for traces in root.findall('Board/Nets/Net/Traces'):
            traces.clear()
        document = io.parse(ET.tostring(root), report=ConversionReport())
        pair = document.one(PAIR)
        self.assertFalse(pair['AutoPadPoints'])
        self.assertEqual(pair.select('PadPoints/PadPoint'), [])

    def test_inherited_pair_widths_use_the_stored_routing_defaults(self):
        def value(node, name, text):
            child = node.find(name)
            if child is None:
                node.set(name, text)
            else:
                child.text = text

        root = automatic_source()
        pair = root.find('Board/DifferentialPairs/DifferentialPair')
        pair.find('PadPoints').clear()
        net_class = root.find("Board/NetClasses/NetClass[@Id='70']")
        value(net_class, 'MaxUncoupledLength', '0')
        for row in net_class.findall('LayProperties/LayProperty'):
            value(row, 'Width', '-1')
            value(row, 'DifClearance', '-1')
        default = root.find('Board/NetClasses/NetClass')
        for row in default.findall('LayProperties/LayProperty'):
            value(row, 'Width', '0.00001')
            value(row, 'Clearance', '0.00001')
        routing = root.find('Board/Settings/Routing')
        value(routing, 'TraceWidth', '1')
        value(routing, 'TraceClearance', '1')
        document = io.parse(ET.tostring(root), report=ConversionReport())
        self.assertEqual(len(document.select(PAIR+'/PadPoints/PadPoint')), 1)
        self.assertEqual(document.one('/Board/Settings/Routing')['TraceWidth'], 3)

    def test_ordered_choices_reconsider_available_negative_pads(self):
        positive = (PadLocation('a', 0, 0), PadLocation('b', 1, 0))
        negative = (PadLocation('x', -2, 0), PadLocation('y', 4, 0))
        self.assertEqual(infer_members(positive, negative, limit=20), (('a', 'x'), ('b', 'y')))

    def test_routed_members_retain_prior_associations(self):
        positive = (PadLocation('a', 0, 0), PadLocation('b', 10, 0))
        negative = (PadLocation('x', 9, 0), PadLocation('y', 1, 0))
        previous = (('a', 'x'), ('b', 'y'))
        self.assertEqual(infer_members(positive, negative, previous=previous,
                                      attached=('a', 'b', 'x', 'y'), limit=20), previous)

    def test_smt_sides_and_static_via_weighting_constrain_inference(self):
        a = PadLocation('a', 0, 0, surface=True)
        b = PadLocation('b', 1, 0, surface=True, side=True)
        self.assertEqual(infer_members((a,), (b,), limit=20), ())
        b = PadLocation('b', 1, 0, static_via=True)
        self.assertEqual(infer_members((a,), (b,), limit=2), ())
        self.assertEqual(infer_members((a,), (b,), limit=2.01), (('a', 'b'),))

    def test_automatic_span_has_a_strict_upper_boundary(self):
        a = PadLocation('a', 0, 0)
        for x, expected in ((99999, (('a', 'b'),)), (100000, ())):
            with self.subTest(x=x):
                self.assertEqual(infer_members((a,), (PadLocation('b', x, 0),), limit=200000), expected)


if __name__ == '__main__':
    unittest.main()
