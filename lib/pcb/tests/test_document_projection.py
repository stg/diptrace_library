"""ASC sheet/display/panel output uses current settings without geometry work."""
import unittest

from lib.common.asc import dumps, loads
from lib.common.conversion import ConversionReport
from lib.common.title_records import new_title_blocks
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.asc.document_projection import project_document_settings
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_asc_core import fixture
from lib.pcb.tests.test_asc_document_settings import source as display_source
from lib.pcb.tests.test_asc_panel import source as panel_source
from lib.pcb.tests.test_component_projection import signature


def design():
    data = loads(display_source())
    board = data.one('/Board')
    for row in tuple(loads(panel_source()).one('/Board').children()):
        if row.kind.startswith('Panelize_'):
            row.move_to(board)
    layers = board.add('NonSignals')
    layers.add('NonSignal', 'Notes', 123, 0, 0)
    layers.add('NonSignal', 'Fabrication', 456, 1, 1)
    visibility = board.add('LayerPanel_NonSignal')
    visibility.add('pt', 'Y')
    visibility.add('pt', 'N')
    return assemble_graphics(prepare_core(dumps(data, preserve=False))).document


def reopen(document, *, report=None):
    data = loads(fixture())
    data.one('/Units').set_values(document.root['Units'])
    board = data.one('/Board')
    layers = board.add('NonSignals')
    for row in document.select('/Board/NonSignals/NonSignal'):
        layers.add('NonSignal', row['Name'], row['Color'], row['Id'], row['Side'])
    for row in tuple(project_document_settings(document.one('/Board'), report=report).children()):
        row.move_to(board)
    return assemble_graphics(prepare_core(dumps(data, preserve=False))).document


def settings_signature(document):
    board = document.one('/Board')
    return {name: signature(board.one(name)) for name in ('Settings', 'SheetSettings', 'Panel')} | {
        'visibility': tuple(row.get('Visible') for row in board.select('NonSignals/NonSignal'))}


class DocumentProjectionTests(unittest.TestCase):
    def test_sheet_display_panel_tabs_and_visibility_round_trip_without_mutation(self):
        document = design()
        before = dumps(document, preserve=False)
        expected = settings_signature(document)
        report = ConversionReport()
        rebuilt = reopen(document, report=report)
        self.assertEqual(settings_signature(rebuilt), expected)
        self.assertEqual(settings_signature(reopen(rebuilt)), expected)
        self.assertEqual(dumps(document, preserve=False), before)
        self.assertEqual(report.notices, [])

    def test_current_order_and_aliases_are_used_with_no_tab_recalculation(self):
        document = design()
        board = document.one('/Board')
        board.one('NonSignals/NonSignal[1]').move_to(board.one('NonSignals'))
        tab = board.one('Panel/HorzTabsX/Item[1]')
        tab['Position'] = 27
        tab.move_to(tab.parent)
        board.one('Panel')['TabWidth'] = 24
        board.one('Settings')['EditInactiveLayer'] = False
        output = project_document_settings(board)
        self.assertEqual([row.values for row in output.select('LayerPanel_NonSignal/pt')], [('N',), ('Y',)])
        self.assertEqual(output['Panelize_TabWidth'], 24)
        self.assertEqual(output.select('Panelize_HorzTabX/pt')[-1].values, (27,))
        self.assertEqual(output.one('Settings')['ContrastEdit'], 'N')
        self.assertEqual(output.one('Settings')['ShowFiducials'], 'N')
        self.assertEqual(settings_signature(reopen(document)), settings_signature(document))
        self.assertTrue(board.one('Panel')['TabsDone'])

    def test_unit_compatibility_switches_follow_one_authoritative_selection(self):
        document = design()
        for unit, expected in (('mm', ('Y', 'N', 'N')), ('mil', ('N', 'Y', 'N')), ('inch', ('N', 'N', 'Y'))):
            document.root['Units'] = unit
            output = project_document_settings(document.one('/Board')).one('Settings')
            self.assertEqual(tuple(output[name] for name in ('UnitsMM', 'UnitsMIL', 'UnitsINCH')), expected)

    def test_omitted_optional_preferences_stay_absent(self):
        document = design()
        board = document.one('/Board')
        del board.one('Settings')['GridSnap']
        del board.one('SheetSettings')['DisplaySheet']
        del board.one('Settings/LayerPanel')['BotOutline']
        output = project_document_settings(board)
        self.assertIsNone(output.one('Settings').child('GridSnap'))
        self.assertIsNone(output.one('Settings').child('DisplaySheet'))
        self.assertIsNone(output.child('LayerPanel_BotOutline'))
        rebuilt = reopen(document)
        self.assertIsNone(rebuilt.one('/Board/Settings').get('GridSnap'))
        self.assertIsNone(rebuilt.one('/Board/SheetSettings').get('DisplaySheet'))

    def test_authored_titles_border_zones_and_nonzero_gaps_warn_on_detached_omission(self):
        document = design()
        board = document.one('/Board')
        sheet = board.one('SheetSettings')
        titles = sheet.append(new_title_blocks())
        titles.one('TitleBlock[1]')['Name'] = 'Company drawing title'
        zones = sheet.add('BorderZones')
        zones['Visible'], zones['HorzZones'] = True, 4
        board.one('Panel')['LeftGap'] = 6
        before = dumps(document, preserve=False)
        report = ConversionReport()
        output = project_document_settings(board, report=report)
        self.assertEqual({notice.rule for notice in report.warnings},
                         {'sheet-title-blocks', 'sheet-border-zones', 'panel-gaps'})
        self.assertFalse(any(row.kind in ('TitleBlocks', 'BorderZones', 'Panelize_LeftGap') for row in output.children()))
        self.assertEqual(dumps(document, preserve=False), before)

    def test_empty_title_anchors_and_zero_gaps_produce_only_information(self):
        document = design()
        board = document.one('/Board')
        board.one('SheetSettings').append(new_title_blocks())
        board.one('Panel')['LeftGap'] = 0
        report = ConversionReport()
        project_document_settings(board, report=report)
        self.assertEqual({notice.rule for notice in report.infos}, {'sheet-title-blocks', 'panel-gaps'})
        self.assertEqual(report.warnings, [])

    def test_visibility_prefix_is_preserved_and_unrepresentable_gaps_fail_explicitly(self):
        document = design()
        board = document.one('/Board')
        first, second = board.select('NonSignals/NonSignal')
        del second['Visible']
        self.assertEqual([row.values for row in project_document_settings(board).select('LayerPanel_NonSignal/pt')], [('Y',)])
        del first['Visible']
        self.assertIsNone(project_document_settings(board).child('LayerPanel_NonSignal'))
        second['Visible'] = False
        before = dumps(document, preserve=False)
        with self.assertRaisesRegex(PcbError, 'all preceding layers'):
            project_document_settings(board)
        self.assertEqual(dumps(document, preserve=False), before)

    def test_unmapped_settings_and_panel_content_fail(self):
        for path in ('Settings', 'Settings/LayerPanel', 'Panel', 'SheetSettings'):
            document = design()
            board = document.one('/Board')
            board.one(path).add('UnmappedSetting', 12)
            before = dumps(document, preserve=False)
            with self.subTest(path=path), self.assertRaises(PcbError):
                project_document_settings(board)
            self.assertEqual(dumps(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
