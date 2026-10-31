"""Missing-component route repair is conditional import modernization."""
import unittest
import xml.etree.ElementTree as ET

from lib.common.conversion import ConversionReport
from lib.common.asc import dumps
from lib.pcb.formats import io
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_core_assembly import fixture
from lib.pcb.tests.test_inactive_electrical import read_core
from lib.pcb.tests.test_dip_output import configured_document


def route(net, first=(999, 5), second=(41, 12), *, points=True):
    traces = net.child('Traces')
    if traces is None:
        traces = net.add('Traces')
    trace = traces.add('Trace')
    for end, (component, pad) in zip(('1', '2'), (first, second)):
        for name, value in (('Connected', 0), ('Object', component),
                            ('SubObject', pad), ('Point', -1)):
            trace.add(name+end, value)
    geometry = trace.add('Points')
    if points:
        for x, y in ((10, 20), (30, 40)):
            point = geometry.add('Point')
            point.add('X', x)
            point.add('Y', y)
    return trace


class NetMemberRepairTests(unittest.TestCase):
    def test_xml_missing_component_reaches_the_shared_import_repair(self):
        data = io.serialize(configured_document(), format='dipxml', report=ConversionReport())
        source = ET.fromstring(data)
        trace = source.find('./Board/Nets/Net/Traces/Trace')
        trace.set('Connected1', 'Pad')
        trace.set('Object1', '999999')
        report = ConversionReport()
        current = io.parse(ET.tostring(source), report=report)
        saved = current.one('/Board/Nets/Net/Traces/Trace[1]')
        self.assertEqual(saved['Connected1'], 'Free')
        self.assertIsNone(saved['Target1'])
        self.assertEqual(len([n for n in report.infos if n.rule == 'missing-component-route-target']), 1)
        self.assertEqual(report.errors, [])
        current.references.validate()

    def test_xml_missing_pad_in_an_existing_component_stays_an_error(self):
        data = io.serialize(configured_document(), format='dipxml', report=ConversionReport())
        source = ET.fromstring(data)
        trace = source.find('./Board/Nets/Net/Traces/Trace')
        self.assertIn(int(trace.get('Object1')),
                      {int(component.get('Id')) for component in source.findall('./Board/Components/Component')})
        trace.set('Connected1', 'Pad')
        trace.set('SubObject1', '999999')
        report = ConversionReport()
        with self.assertRaisesRegex(PcbError, 'unresolved XML pad reference'):
            io.parse(ET.tostring(source), report=report)
        self.assertEqual(len(report.errors), 1)
        self.assertFalse(any(n.rule == 'missing-component-route-target' for n in report.notices))

    def test_repaired_asc_converts_stably_without_repairing_again(self):
        syntax = io.project(configured_document(), format='asc', report=ConversionReport())
        trace = syntax.one('/Board/Nets/Net/Lines/Line[1]')
        trace.one('ConnectMode1').set_values(0)
        trace.one('Connect1').set_values(999999)
        text = dumps(syntax, preserve=False)
        # Explicit source inspection exposes the supplied syntax unchanged.
        inspected = io.parse_source(text)
        self.assertEqual(inspected.one(trace.path+'/Connect1').values, (999999,))
        report = ConversionReport()
        current = io.parse(text, report=report)
        saved = current.one('/Board/Nets/Net/Traces/Trace[1]')
        self.assertEqual(saved['Connected1'], 'Free')
        self.assertIsNone(saved['Target1'])
        self.assertEqual(len([n for n in report.infos if n.rule == 'missing-component-route-target']), 1)
        geometry = [(p['X'], p['Y']) for p in saved.select('Points/Point')]
        for format in ('dip', 'asc', 'dipxml'):
            with self.subTest(format=format):
                data = io.serialize(current, format=format, report=ConversionReport())
                rebuilt_report = ConversionReport()
                rebuilt = io.parse(data, report=rebuilt_report)
                rebuilt_trace = rebuilt.one('/Board/Nets/Net/Traces/Trace[1]')
                self.assertEqual(rebuilt_trace['Connected1'], 'Free')
                self.assertEqual([(p['X'], p['Y']) for p in rebuilt_trace.select('Points/Point')], geometry)
                self.assertFalse(any(n.rule == 'missing-component-route-target' for n in rebuilt_report.notices))
                # Destination defaults may materialize on its first import.
                # Further cycles must not repeat the repair or accumulate edits.
                normalized = io.serialize(rebuilt, format=format, report=ConversionReport())
                again_report = ConversionReport()
                again = io.parse(normalized, report=again_report)
                self.assertEqual(io.serialize(again, format=format, report=ConversionReport()), normalized)
                self.assertFalse(any(n.rule == 'missing-component-route-target' for n in again_report.notices))
                rebuilt.references.validate()

    def test_missing_component_frees_only_its_endpoint_and_keeps_geometry(self):
        inputs = fixture()
        net = inputs.board.one('Nets/Net')
        trace = route(net)
        points = trace.select('Points/Point')
        report = ConversionReport()
        document = read_core(inputs, report=report)
        pads = document.one('/Board/Components/Component/Pattern/Pads').children('Pad')
        self.assertEqual((trace['Connected1'], trace['Connected2']), (-1, 0))
        self.assertEqual(trace.select('Points/Point'), points)
        self.assertEqual([(p['X'], p['Y']) for p in points], [(10, 20), (30, 40)])
        self.assertIs(net.one('Pads/Item')['Pad'], pads[1])
        # A surviving, unlisted assignment remains meaningful and searchable.
        self.assertIs(pads[0]['Net'], net)
        self.assertEqual(len(document.references.outgoing(pads[0], role='pad-net')), 1)
        notices = [n for n in report.notices if n.rule == 'missing-component-route-target']
        self.assertEqual(len(notices), 1)
        self.assertEqual((notices[0].severity, notices[0].operation), ('info', 'import'))
        document.references.validate()

    def test_member_order_comes_from_surviving_endpoints_without_duplicates(self):
        inputs = fixture()
        net = inputs.board.one('Nets/Net')
        route(net)
        route(net, (41, 5), (41, 12))
        route(net, (41, 5), (41, 5))
        result = assemble_core(inputs)
        self.assertEqual([row['Pad'] for row in net.select('Pads/Item')],
                         [result.pads[41, 12], result.pads[41, 5]])
        result.document.references.validate()

    def test_no_trace_and_existing_free_end_do_not_rebuild_members(self):
        for free_end in (False, True):
            with self.subTest(free_end=free_end):
                inputs = fixture()
                net = inputs.board.one('Nets/Net')
                if free_end:
                    trace = route(net)
                    trace.one('Connected1').set_values(-1)
                original = net.one('Pads/Item')
                report = ConversionReport()
                document = read_core(inputs, report=report)
                self.assertIs(net.one('Pads/Item'), original)
                self.assertIs(original['Pad'], document.one('/Board/Components/Component/Pattern/Pads/Pad[1]'))
                self.assertFalse(any(n.rule == 'missing-component-route-target' for n in report.notices))

    def test_an_affected_net_does_not_rebuild_other_nets(self):
        inputs = fixture()
        net = inputs.board.one('Nets/Net')
        other = net.parent.append(net.clone())
        other.one('Number').set_values(74)
        other.one('Name').set_values('Other')
        other.one('Pads/Item').set_values(41, 5)
        inputs.board.one('Components/Component/Pattern/Pads').children('Pad')[2].one('NetNumber').set_values(74)
        route(other, (999, 5), (41, 12))
        original = net.one('Pads/Item')
        result = assemble_core(inputs)
        self.assertIs(net.one('Pads/Item'), original)
        self.assertIs(original['Pad'], result.pads[41, 5])
        self.assertIs(other.one('Pads/Item')['Pad'], result.pads[41, 12])
        result.document.references.validate()

    def test_deleted_component_target_is_absent_and_its_stale_member_is_removed(self):
        inputs = fixture()
        component = inputs.board.one('Components/Component')
        component.one('Enabled').set_values(False)
        net = inputs.board.one('Nets/Net')
        trace = route(net, (41, 5), (41, 12))
        result = assemble_core(inputs)
        self.assertEqual((trace['Connected1'], trace['Connected2']), (-1, -1))
        self.assertEqual(net.select('Pads/Item'), [])
        self.assertIsNone(component.parent)
        result.document.references.validate()

    def test_reconciliation_refreshes_a_surviving_pad_assignment(self):
        inputs = fixture()
        pad = inputs.board.one('Components/Component/Pattern/Pads').children('Pad')[2]
        pad.one('NetNumber').set_values(-1)
        net = inputs.board.one('Nets/Net')
        route(net)
        result = assemble_core(inputs)
        self.assertIs(pad['Net'], net)
        self.assertIs(net.one('Pads/Item')['Pad'], pad)
        result.document.references.validate()

    def test_invalid_pad_is_freed_only_during_an_already_required_reconciliation(self):
        inputs = fixture()
        net = inputs.board.one('Nets/Net')
        trace = route(net, (999, 5), (41, 999))
        result = assemble_core(inputs)
        self.assertEqual((trace['Connected1'], trace['Connected2']), (-1, -1))
        self.assertEqual(net.select('Pads/Item'), [])
        self.assertIs(result.pads[41, 5]['Net'], net)

    def test_empty_traces_do_not_supply_rebuilt_members(self):
        inputs = fixture()
        net = inputs.board.one('Nets/Net')
        route(net)
        route(net, (41, 5), (41, 5), points=False)
        result = assemble_core(inputs)
        self.assertEqual([row['Pad'] for row in net.select('Pads/Item')], [result.pads[41, 12]])

    def test_repair_does_not_guess_between_ambiguous_pad_identities(self):
        inputs = fixture()
        component = inputs.board.one('Components/Component')
        duplicate = component.parent.append(component.clone())
        duplicate.one('RefDes').set_values('U2')
        trace = route(inputs.board.one('Nets/Net'))
        with self.assertRaisesRegex(PcbError, 'ambiguous saved net pad reference'):
            assemble_core(inputs)
        self.assertEqual(trace['Connected1'], 0)
        self.assertIsNone(inputs.root._document)

    def test_repeated_component_numbers_with_distinct_pad_keys_are_not_missing(self):
        inputs = fixture()
        component = inputs.board.one('Components/Component')
        duplicate = component.parent.append(component.clone())
        duplicate.one('RefDes').set_values('U2')
        for pad, key in zip(duplicate.one('Pattern/Pads').children('Pad')[1:-1], (25, 26)):
            pad.one('Number_New').set_values(key)
        net = inputs.board.one('Nets/Net')
        route(net, (999, 5), (41, 25))
        result = assemble_core(inputs)
        self.assertIs(net.one('Pads/Item')['Pad'], result.pads[41, 25])
        self.assertEqual(len(result.components.records), 2)
        result.document.references.validate()

    def test_failure_elsewhere_does_not_partially_apply_a_planned_repair(self):
        inputs = fixture()
        net = inputs.board.one('Nets/Net')
        trace = route(net)
        original = net.one('Pads/Item')
        other = net.parent.append(net.clone())
        other.one('Number').set_values(74)
        other.one('Name').set_values('Other')
        other.one('Traces').detach()
        other.one('Pads/Item').set_values(999, 999)
        with self.assertRaisesRegex(PcbError, 'unresolved saved net pad key'):
            assemble_core(inputs)
        self.assertEqual(trace['Connected1'], 0)
        self.assertIs(net.one('Pads/Item'), original)
        self.assertEqual(original.values, (41, 5))
        self.assertIsNone(inputs.root._document)


if __name__ == '__main__':
    unittest.main()
