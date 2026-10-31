"""Complete current binary streams reopen after data edits without source I/O."""
from decimal import Decimal
from pathlib import Path
import unittest
from unittest.mock import patch

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport, import_diagnostics
from lib.common.schema import MISSING
from lib.common.title_records import new_title_blocks
from lib.pcb.formats.dip.decode import decode
from lib.pcb.formats.dip.write import encode
from lib.pcb.formats.import_context import ImportContext
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.formats.assembly.routing import assemble_routing
from lib.pcb.formats.assembly.board_rules import assemble_rules
from lib.pcb.tests.test_cache_projection import signature
from lib.pcb.tests.test_xml_document_output import design as xml_design
from lib.pcb.tests.test_dipxml_pairs import source as pair_source
from lib.pcb.tests.test_dipxml_library import source as library_source
from lib.pcb.tests.test_drc_length_targets import source as length_source, error as length_error
from lib.pcb.tests.test_pair_projection import signature as pair_signature
from lib.pcb.tests.test_xml_routing_output import with_component_library


def configured_document(text=None):
    """Synthetic configuration choices for a portable complete-stream fixture.

    These explicit zero/empty selections are test data, not the application's
    defaults or the production export-context policy.
    """
    document = xml_design(text)
    board = document.one('/Board')
    # DIP uses application preferences for these choices. Most fixtures omit
    # them; a separate test checks that explicit choices warn on projection.
    pending = {'GridSnap', 'AssemblyWidth', 'CompOutlineWidth', 'CourtyardWidth'}
    for node in (board, *board.children('Settings')):
        for name in pending:
            if node.child(name) is not None:
                del node[name]
    for path in ('Settings/Routing', 'Settings/LayerPanel', 'SheetSettings/BorderZones',
                 'Panel', 'DRC', 'LastDRC', 'ConnectivityCheck'):
        node = board
        for name in path.split('/'):
            node = node.child(name) if node.child(name) is not None else node.add(name)
    if board.one('SheetSettings').child('TitleBlocks') is None:
        board.one('SheetSettings').append(new_title_blocks())
    for node in (board, *[board.one(path) for path in (
            'Settings', 'Settings/Routing', 'Settings/LayerPanel', 'SheetSettings',
            'SheetSettings/BorderZones', 'Panel', 'DRC', 'LastDRC', 'ConnectivityCheck')]):
        for name, field in node.schema.fields.items():
            if name in pending:
                continue
            if field.getter is not None or field.kind not in ('text', 'integer', 'number', 'boolean'):
                continue
            if node.get(name, MISSING) is MISSING and field.default is MISSING:
                node[name] = {'text': '', 'integer': 0, 'number': 0, 'boolean': False}[field.kind]
    board['CompFontSize'], board['PatternFontScale'] = 2, 1
    for pad in board.select('Components/Component/Pattern/Pads/Pad'):
        if pad.child('Id') is not None:
            del pad['Id']
    for pattern in board.select('Components/Component/Pattern'):
        if pattern.child('Sided') is not None:
            del pattern['Sided']
    return document


def assemble_preserving_colors(decoded):
    # Exact wire comparisons use an explicit neutral display environment.
    # Canvas-contrast modernization is covered by the import/color tests.
    core = assemble_core(decoded, context=ImportContext(background_color=None))
    routed = assemble_routing(decoded, core)
    rules = assemble_rules(decoded, routed)
    return assemble_graphics(decoded, rules).document


@import_diagnostics('dip')
def reopen(data):
    return assemble_preserving_colors(decode(data))


class DipOutputTests(unittest.TestCase):
    def test_complete_stream_reopens_and_repeated_binary_output_stabilizes(self):
        document = configured_document()
        before = dumps(document, preserve=False)
        report = ConversionReport()
        with patch.object(Path, 'open', side_effect=AssertionError('external file access')):
            data = encode(document, report=report)
            rebuilt = reopen(data, report=ConversionReport())
            self.assertEqual(encode(rebuilt, report=ConversionReport()), data)
        self.assertEqual(dumps(document, preserve=False), before)
        self.assertEqual(data[:8], b'\x07DTBOARD')
        self.assertEqual(decode(data).header.version, 62)
        rebuilt.references.validate()

    def test_component_and_net_edits_remain_authoritative_in_complete_output(self):
        document = configured_document()
        component = document.one('/Board/Components/Component')
        component['RefDes'], component['Value'], component['X'] = 'U17', 'Edited', Decimal('31.25')
        net = document.one('/Board/Nets/Net')
        net['Name'] = 'Edited net'
        point = net.one('Traces/Trace[1]/Points/Point[2]')
        point.move_to(point.parent, 0)
        rebuilt = reopen(encode(document, report=ConversionReport()), report=ConversionReport())
        saved = rebuilt.one('/Board/Components/Component')
        self.assertEqual((saved['RefDes'], saved['Value'], saved['X']), ('U17', 'Edited', Decimal('31.25')))
        self.assertEqual(rebuilt.one('/Board/Nets/Net')['Name'], 'Edited net')
        current = rebuilt.one('/Board/Nets/Net/Traces/Trace[1]/Points/Point[1]')
        self.assertEqual((current['X'], current['Y']), (point['X'], point['Y']))
        actual = signature(saved)
        expected = signature(component)
        self.assertEqual({name: actual[name] for name in expected}, expected)

    def test_application_preferences_warn_without_changing_the_source(self):
        document = configured_document()
        settings = document.one('/Board/Settings')
        preferences = dict(GridSnap=False, AssemblyWidth=Decimal('.5'),
                           CompOutlineWidth=Decimal('.6'), CourtyardWidth=Decimal('.7'))
        for name, value in preferences.items():
            settings[name] = value
        before, report = dumps(document, preserve=False), ConversionReport()
        rebuilt = reopen(encode(document, report=report), report=ConversionReport())
        notices = [notice for notice in report.warnings if notice.rule == 'application-preferences']
        self.assertEqual(len(notices), 1)
        notice = notices[0]
        self.assertEqual(notice.rule, 'application-preferences')
        for name in preferences:
            self.assertIn(name, notice.message)
            self.assertIsNone(rebuilt.one('/Board/Settings').child(name))
        self.assertEqual(dumps(document, preserve=False), before)

    def test_xml_import_exports_without_manually_completing_optional_settings(self):
        document = xml_design()
        before, report = dumps(document, preserve=False), ConversionReport()
        data = encode(document, report=report)
        rebuilt = reopen(data, report=ConversionReport())
        self.assertEqual(rebuilt.one('/Board')['ShieldGroup'], document.one('/Board')['ShieldGroup'])
        self.assertEqual(rebuilt.one('/Board')['LockNetStructure'], document.one('/Board')['LockNetStructure'])
        self.assertEqual(encode(rebuilt, report=ConversionReport()), data)
        self.assertEqual(dumps(document, preserve=False), before)
        rebuilt.references.validate()

    def test_connection_lock_and_text_flip_remain_independent(self):
        for locked in (False, True):
            document = configured_document()
            board = document.one('/Board')
            board['LockNetStructure'] = locked
            board.one('Settings')['FlipTextAuto'] = not locked
            with self.subTest(locked=locked):
                data = encode(document, report=ConversionReport())
                rebuilt = reopen(data, report=ConversionReport())
                self.assertEqual(rebuilt.one('/Board')['LockNetStructure'], locked)
                self.assertEqual(rebuilt.one('/Board/Settings')['FlipTextAuto'], not locked)
                self.assertEqual(encode(rebuilt, report=ConversionReport()), data)

    def test_secondary_symbol_without_footprint_gets_an_empty_binary_envelope(self):
        document = configured_document(library_source())
        slot = document.one('/Board/CacheLib/Slots/Slot')
        first = slot.one('Definition')
        second = slot.add('Definition', 0)
        document.copy(first.one('Part'), parent=second)
        before = dumps(document, preserve=False)
        data = encode(document, report=ConversionReport())
        rebuilt = reopen(data, report=ConversionReport())
        saved = rebuilt.one(second.path)
        self.assertEqual(saved.one('Pattern')['Name'], '')
        self.assertEqual(saved.select('Pattern/Pads/Pad'), [])
        pin = saved.one('Part/Pins/Pin')
        binding, = rebuilt.references.outgoing(saved.one('Part'), role='symbol-pin-pad')
        self.assertIs(binding.target.parent.parent, rebuilt.one(first.path+'/Pattern'))
        self.assertEqual(pin['Number'], second.one('Part/Pins/Pin')['Number'])
        self.assertEqual(encode(rebuilt, report=ConversionReport()), data)
        self.assertIsNone(second.child('Pattern'))
        self.assertEqual(dumps(document, preserve=False), before)
        rebuilt.references.validate()

    def test_reordered_cache_definitions_project_the_assigned_footprint_first(self):
        document = configured_document(library_source())
        slot = document.one('/Board/CacheLib/Slots/Slot')
        primary = slot.one('Definition')
        primary.one('Part')['PartName'] = 'Primary section'
        primary.one('Pattern')['Name'] = 'Assigned footprint'
        independent = slot.add('Definition', 0)
        document.copy(primary.one('Part'), parent=independent)['PartName'] = 'Other section'
        document.copy(primary.one('Pattern'), parent=independent)['Name'] = 'Independent footprint'
        primary.move_to(slot)
        before = dumps(document, preserve=False)
        for version in (54, 62):
            with self.subTest(version=version):
                report = ConversionReport()
                data = encode(document, version=version, report=report)
                rebuilt = reopen(data, report=ConversionReport())
                saved = rebuilt.one(slot.path)
                first, second = saved.children('Definition')
                self.assertEqual((first.one('Part')['PartName'], first.one('Pattern')['Name']),
                                 ('Primary section', 'Assigned footprint'))
                self.assertEqual((second.one('Part')['PartName'], second.one('Pattern')['Name']),
                                 ('Other section', 'Independent footprint'))
                for definition in saved.children('Definition'):
                    binding, = rebuilt.references.outgoing(definition.one('Part'), role='symbol-pin-pad')
                    self.assertIs(binding.target.parent.parent, first.one('Pattern'))
                self.assertIn('cached-footprint-order', [notice.rule for notice in report.infos])
                self.assertEqual(encode(rebuilt, version=version, report=ConversionReport()), data)
                rebuilt.references.validate()
        self.assertEqual(slot.children('Definition'), [independent, primary])
        self.assertEqual(dumps(document, preserve=False), before)

    def test_pair_geometry_and_reference_graph_survive_the_complete_stream(self):
        document = configured_document(with_component_library(pair_source()))
        expected = pair_signature(document)
        rebuilt = reopen(encode(document, report=ConversionReport()), report=ConversionReport())
        self.assertEqual(pair_signature(rebuilt), expected)
        rebuilt.references.validate()

    def test_cached_definitions_keep_pin_assignments_and_paths_in_complete_output(self):
        document = configured_document(library_source())
        definition = document.one('/Board/CacheLib/Slots/Slot/Definition')
        definition.one('Part')['Datasheet'] = 'docs/device.pdf'
        definition.one('Pattern/Pads/Pad[1]').move_to(definition.one('Pattern/Pads'))
        rebuilt = reopen(encode(document, report=ConversionReport()), report=ConversionReport())
        actual = rebuilt.one('/Board/CacheLib/Slots/Slot/Definition')
        self.assertEqual(actual.one('Part')['Datasheet'], 'docs/device.pdf')
        self.assertEqual(actual.one('Part/Pins/Pin')['Number'], 2)
        self.assertEqual(actual.one('Pattern/Pads/Pad[2]')['StringNumber'],
                         definition.one('Pattern/Pads/Pad[2]')['StringNumber'])
        self.assertEqual(rebuilt.one('/Board/CacheLib/Slots/Slot')['VariablePath'],
                         document.one('/Board/CacheLib/Slots/Slot')['VariablePath'])
        rebuilt.references.validate()

    def test_generated_class_length_policies_and_saved_results_share_output_order(self):
        document = configured_document(with_component_library(length_source(length_error(0), length_error(1))))
        board = document.one('/Board')
        first, second = board.select('NetClasses/NetClass')
        first['CheckLength'] = True
        board['DefaultClass'] = second
        row = board.one('DesignErrors/DesignError[2]')
        row['NetClass1'] = second
        rebuilt = reopen(encode(document, report=ConversionReport()), report=ConversionReport())
        actual = rebuilt.one('/Board/DesignErrors/DesignError[2]')
        self.assertEqual(actual['Target1'].parent.parent.parent['Name'], second['Name'])
        self.assertEqual(actual['NetClass1']['Name'], second['Name'])
        self.assertEqual((actual['Value'], actual['Rule']), (row['Value'], row['Rule']))

    def test_teardrop_membership_and_shield_ids_remain_current_data(self):
        document = configured_document()
        board, net = document.one('/Board'), document.one('/Board/Nets/Net')
        polygons = net.one('Teardrops')
        polygon = polygons.add('Teardrop')
        polygon['Layer'] = board.one('Layers/Layer[1]')
        polygon['DrawX'], polygon['DrawY'] = Decimal('1.25'), Decimal('2.5')
        points = polygon.add('Points')
        for x, y in ((1, 1), (3, 1), (3, 2)):
            points.add('pt', x, y)
        trace = net.one('Traces/Trace[1]')
        member = trace.one('ConnectedTeardrops').add('Item')
        member['Teardrop'] = polygon
        document.copy(polygon, index=0)
        board.one('Components/Component')['ShieldGroup'] = 7
        board.one('Components/Component/Pattern/Pads/Pad[1]')['ShieldGroup'] = 9
        point = trace.one('Points/Point[1]')
        point['ShieldGroup'] = 13
        board.one('CopperPours/CopperPour')['TraceShieldGroup'] = 17
        board['ShieldGroup'] = 19
        data = encode(document, report=ConversionReport())
        self.assertEqual(decode(data).board['ShieldGroup'], 19)
        rebuilt = reopen(data, report=ConversionReport())
        self.assertEqual(rebuilt.one('/Board')['ShieldGroup'], 19)
        saved = rebuilt.one(member.path)
        self.assertEqual(saved['Teardrop']._ordinal(), polygon._ordinal())
        self.assertEqual(saved['Teardrop']['DrawX'], Decimal('1.25'))
        self.assertEqual(rebuilt.one(point.path)['ShieldGroup'], 13)
        self.assertEqual(encode(rebuilt, report=ConversionReport()), data)
        rebuilt.references.validate()


if __name__ == '__main__':
    unittest.main()
