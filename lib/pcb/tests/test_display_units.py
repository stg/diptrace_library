"""One editable display choice replaces binary menu-switch snapshots."""
from itertools import product
from types import SimpleNamespace
import unittest

from lib.pcb.formats.import_context import ImportContext
from lib.pcb.formats.assembly.assemble import assemble_core
from lib.pcb.formats.dip.settings import DisplayUpgrade
from lib.pcb.model.objects import new_document
from lib.pcb.model import settings_records
from lib.pcb.tests.test_core_assembly import fixture


class DisplayUnitTests(unittest.TestCase):
    def test_display_settings_and_camera_have_typed_editable_fields(self):
        decoded = fixture()
        decoded.root.add('Scale', 100)
        decoded.root.add('Xpos', 1)
        decoded.root.add('Ypos', -2)
        settings = decoded.board.add('Settings')
        settings.add('GridSize', 3)
        settings.add('GridEnabled', True)
        panel = settings.add('LayerPanel')
        panel.add('TopAssy', True)
        check = decoded.board.add('ConnectivityCheck')
        check.add('Traces', True)
        result = assemble_core(decoded)
        self.assertIs(settings.schema, settings_records.SETTINGS)
        self.assertIs(panel.schema, settings_records.LAYER_PANEL)
        self.assertIs(check.schema, settings_records.CONNECTIVITY)
        settings['GridSize'] = 6
        panel['TopAssy'] = False
        check['Traces'] = False
        result.document.root['Xpos'] = 7
        self.assertEqual(result.components[41]['X'], 0)
        self.assertEqual(result.document.root['Xpos'], 7)
        with self.assertRaises(TypeError):
            settings['GridEnabled'] = 1
        self.assertTrue(settings['GridEnabled'])
        copied = result.document.clone()
        copied.one('/Board/Settings')['GridSize'] = 12
        self.assertEqual(settings['GridSize'], 6)

    def test_import_consumes_switches_with_last_selected_precedence(self):
        for choices in product((False, True), repeat=3):
            with self.subTest(choices=choices):
                decoded = fixture()
                settings = decoded.board.add('Settings')
                decoded.upgrades = SimpleNamespace(display=DisplayUpgrade(settings, choices))
                result = assemble_core(decoded, context=ImportContext(units='mil'))
                expected = 'mil'
                for selected, unit in zip(choices, ('mm', 'mil', 'inch')):
                    if selected:
                        expected = unit
                self.assertEqual(result.document.root['Units'], expected)
                self.assertEqual(result.components[41]['X'], 0)
                self.assertFalse(any(settings.child(name) for name in ('UnitsMM', 'UnitsMIL', 'UnitsINCH')))

    def test_default_and_overridden_environment_are_materialized(self):
        self.assertEqual(assemble_core(fixture()).document.root['Units'], 'mm')
        document = assemble_core(fixture(), context=ImportContext(units='in')).document
        self.assertEqual(document.root['Units'], 'inch')
        self.assertEqual(new_document().root['Units'], 'mm')

    def test_context_validation_precedes_input_mutation(self):
        decoded = fixture()
        with self.assertRaises(TypeError):
            assemble_core(decoded, context='mil')
        self.assertIsNone(decoded.root._document)
        for invalid in ('cm', '', 'MM'):
            with self.assertRaises(ValueError):
                ImportContext(units=invalid)
        with self.assertRaises(TypeError):
            ImportContext(units=None)

    def test_editing_units_never_rescales_geometry_and_clones_are_independent(self):
        result = assemble_core(fixture())
        document = result.document
        component = result.components[41]
        component['X'], component['Y'] = 12, -3
        document.root['Units'] = 'inch'
        self.assertEqual((component['X'], component['Y']), (12, -3))
        copied = document.clone()
        copied.root['Units'] = 'mil'
        self.assertEqual(document.root['Units'], 'inch')
        self.assertEqual(copied.one('/Board/Components/Component')['X'], 12)
        with self.assertRaisesRegex(ValueError, 'must be one of'):
            document.root['Units'] = 'cm'
        self.assertEqual(document.root['Units'], 'inch')
        with self.assertRaises(TypeError):
            del document.root['Units']


if __name__ == '__main__':
    unittest.main()
