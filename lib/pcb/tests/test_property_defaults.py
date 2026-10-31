"""Earlier settings become ordinary current data at their individual gates."""
from decimal import Decimal
from types import SimpleNamespace
import unittest

from lib.common.conversion import ConversionReport, import_diagnostics
from lib.common.model import Document, Element
from lib.pcb.formats.dip.property_defaults import modernize_properties


def fixture(version):
    board = Element('Board')
    board.add('PanelDX', 0)
    board.add('PanelDY', 0)
    placed = board.add('Components').add('Component').add('Pattern').add('Model3D')
    definition = board.add('CacheLib').add('Slots').add('Slot').add('Definition')
    cached = definition.add('Pattern').add('Model3D')
    pin = definition.add('Part').add('Pins').add('Pin')
    return SimpleNamespace(board=board, header=SimpleNamespace(version=version)), placed, cached, pin


class PropertyDefaultsTests(unittest.TestCase):
    def test_older_title_fields_have_the_current_line_spacing_at_each_anchor(self):
        for version in (31, 39, 46, 47, 62):
            with self.subTest(version=version):
                decoded, _, _, _ = fixture(version)
                titles = decoded.board.add('SheetSettings').add('TitleBlocks')
                fields = [titles.add('TitleBlock', index).add('Contents').add('Content', 0)
                          for index in range(6)]
                modernize_properties(decoded)
                for field in fields:
                    self.assertEqual(field.get('LineSpacing'), Decimal('1.2') if version < 47 else None)
                if version < 47:
                    fields[0].one('LineSpacing').set_values(Decimal('1.7'))
                    modernize_properties(decoded)
                    self.assertEqual(fields[0]['LineSpacing'], Decimal('1.7'))

    def test_introduction_gates_apply_to_placed_and_cached_model_settings(self):
        for version in (31, 39, 46, 47, 48, 49, 50, 62):
            with self.subTest(version=version):
                decoded, placed, cached, pin = fixture(version)
                modernize_properties(decoded)
                for model in (placed, cached):
                    self.assertEqual(model.get('IPC_XOff'), 0 if version < 47 else None)
                    self.assertEqual(model.get('IPC_YOff'), 0 if version < 47 else None)
                    self.assertEqual(model.get('AutoHeight'), 0 if version < 47 else None)
                    self.assertEqual(model.get('AutoColor'), 0x4B4B4B if version < 47 else None)
                    self.assertEqual(model.get('Type'), 0 if version < 47 else None)
                    self.assertIs(model.get('KeepPins'), False if version < 50 else None)
                    self.assertIsNone(model.child('Model3DFile_Variable'))
                self.assertEqual(pin.get('PinNameRotate'), 0 if version < 48 else None)
                self.assertEqual(pin.get('PinNumRotate'), 0 if version < 48 else None)

    def test_authored_properties_and_paths_remain_independent(self):
        decoded, placed, cached, pin = fixture(49)
        for model in (placed, cached):
            model.add('KeepPins', True)
            model.add('AutoColor', 0x123456)
            model.add('Model3DFile', 'parts/package.step')
            model.add('Model3DFile_Variable', '%projectdir%/parts/package.step')
        pin.add('PinNameRotate', 1)
        pin.add('PinNumRotate', 2)
        modernize_properties(decoded)
        for model in (placed, cached):
            self.assertTrue(model['KeepPins'])
            self.assertEqual(model['AutoColor'], 0x123456)
            self.assertEqual(model['Model3DFile_Variable'], '%projectdir%/parts/package.step')
        self.assertEqual((pin['PinNameRotate'], pin['PinNumRotate']), (1, 2))

    def test_modernization_reports_once_and_does_not_store_history(self):
        decoded, placed, cached, pin = fixture(46)

        @import_diagnostics('dip')
        def load():
            modernize_properties(decoded)
            return Document(Element(''))

        report = ConversionReport()
        load(report=report)
        self.assertEqual(len(report.infos), 1)
        self.assertEqual(report.infos[0].rule, 'legacy-board-properties')
        self.assertEqual(len(report.infos[0].paths), 4)
        self.assertFalse(report.warnings)
        self.assertFalse(report.errors)
        self.assertTrue(all(not node.annotations for node in decoded.board.walk(include_self=True)))
        load(report=report)
        self.assertEqual(len(report.infos), 1)

    def test_earlier_panel_gaps_modernize_from_spacing_once_and_then_edit_independently(self):
        for version in (50, 54, 55, 62):
            decoded, _, _, _ = fixture(version)
            decoded.board.set_field('PanelDX', 7)
            decoded.board.set_field('PanelDY', 11)
            panel = decoded.board.add('Panel')
            modernize_properties(decoded)
            if version < 55:
                self.assertEqual([panel[name] for name in ('LeftGap', 'RightGap', 'TopGap', 'BottomGap')],
                                 [7, 7, 11, 11])
                panel.set_field('LeftGap', 3)
                decoded.board.set_field('PanelDX', 17)
                modernize_properties(decoded)
                self.assertEqual((panel['LeftGap'], panel['RightGap']), (3, 7))
            else:
                self.assertIsNone(panel.child('LeftGap'))

    def test_panel_authoring_configuration_is_supplied_only_before_its_saved_record(self):
        expected = dict(Type=0, BorderTabs=0, TabsDone=False, KeepMaterial=False,
            TabWidth=Decimal('13.5'), TabRadius=Decimal('3.6'), TabStep=225,
            HoleDiam=Decimal('2.4'), HoleStep=Decimal('3.6'), HoleInset=0,
            HoleKeepout=3, CombinedRadius=Decimal('3.6'))
        for version in (31, 46, 49, 50, 62):
            with self.subTest(version=version):
                decoded, _, _, _ = fixture(version)
                modernize_properties(decoded)
                panel = decoded.board.child('Panel')
                if version >= 50:
                    self.assertIsNone(panel)
                    continue
                self.assertEqual({name: panel[name] for name in expected}, expected)
                for name in ('HorzTabsX', 'VertTabsY'):
                    self.assertFalse(panel.one(name).children())

    def test_panel_defaults_do_not_replace_saved_or_subsequently_edited_settings(self):
        for version in (49, 50):
            with self.subTest(version=version):
                decoded, _, _, _ = fixture(version)
                panel = decoded.board.add('Panel')
                panel.add('TabStep', 99)
                panel.add('TabWidth', Decimal('7.25'))
                positions = panel.add('HorzTabsX')
                positions.add('Item', 17)
                modernize_properties(decoded)
                self.assertEqual((panel['TabStep'], panel['TabWidth']), (99, Decimal('7.25')))
                panel.set_field('TabStep', 123)
                modernize_properties(decoded)
                self.assertEqual(panel['TabStep'], 123)
                self.assertEqual([row.values for row in positions.children()], [(17,)])
