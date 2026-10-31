"""Literal-only binary revisions modernize into ordinary current path fields."""
from types import SimpleNamespace
import unittest

from lib.common.model import Element
from lib.pcb.formats.dip.paths import read_variable_paths


def board():
    root = Element('Board')
    root.add('RelSchem', 'projects/design.dch')
    root.add('ProjectLibs_Type', 2)
    root.add('Panel')
    components = root.add('Components')
    component = components.add('Component')
    component.add('Enabled', True)
    component.add('LibPath', 'libraries/components.eli')
    model = component.add('Pattern').add('Model3D')
    model.add('Model3DFile', 'models/device.wrl')
    disabled = components.add('Component')
    disabled.add('Enabled', False)
    disabled.add('LibPath', 'disabled.eli')
    disabled.add('Pattern').add('Model3D').add('Model3DFile', '')
    picture = root.add('Shapes').add('Shape')
    picture.add('Enabled', True)
    picture.add('Picture_File', 'pictures/logo.bmp')
    root.add('ProjectLibs_Folders').add('Folder', 'libraries')
    root.add('ProjectLibs_Libs').add('Lib', 'libraries/patterns.lib')
    slot = root.add('CacheLib').add('Slots').add('Slot', 17, 'libraries/cache.lib')
    cached = slot.add('Definition').add('Pattern').add('Model3D')
    cached.add('Model3DFile', 'models/template.wrl')
    return root


class LegacyVariablePathTests(unittest.TestCase):
    def test_older_revisions_initialize_each_literal_path_domain_without_reading_more_data(self):
        for version in (31, 46, 52):
            with self.subTest(version=version):
                current = board()
                reader = SimpleNamespace(header=SimpleNamespace(version=version))
                self.assertFalse(read_variable_paths(reader, current))
                expected = {
                    'RelSchem_Variable': 'projects/design.dch',
                    'Components/Component[1]/LibPath_Variable': 'libraries/components.eli',
                    'Components/Component[1]/Pattern/Model3D/Model3DFile_Variable': 'models/device.wrl',
                    'Shapes/Shape/Picture_File_Variable': 'pictures/logo.bmp',
                    'ProjectLibs_Folders/Folder/VariablePath': 'libraries',
                    'ProjectLibs_Libs/Lib/VariablePath': 'libraries/patterns.lib',
                    'CacheLib/Slots/Slot/VariablePath': 'libraries/cache.lib'}
                for path, value in expected.items():
                    self.assertEqual(current.one(path).values, (value,))
                self.assertIsNone(current.one('Components/Component[2]').child('LibPath_Variable'))
                self.assertIsNone(current.one('CacheLib/Slots/Slot/Definition/Pattern/Model3D').child(
                    'Model3DFile_Variable'))  # Cached model defaults have a separate scope.

    def test_completion_is_idempotent_and_does_not_overwrite_an_explicit_value(self):
        current = board()
        current.add('RelSchem_Variable', '')
        field = current.one('Components/Component[1]').add('LibPath_Variable', '${PARTS}/device.eli')
        reader = SimpleNamespace(header=SimpleNamespace(version=52))
        read_variable_paths(reader, current)
        count = sum(1 for _ in current.walk())
        read_variable_paths(reader, current)
        self.assertEqual(sum(1 for _ in current.walk()), count)
        self.assertEqual(field.values, ('${PARTS}/device.eli',))
        self.assertEqual(current.one('RelSchem_Variable').values, ('',))

    def test_modern_serialized_empty_or_variable_paths_remain_authoritative(self):
        class Reader:
            header = SimpleNamespace(version=53)

            def field(self, owner, name, kind):
                owner.add(name, False if kind == 'boolean' else '')

            def boolean(self):
                return False

        current = board()
        self.assertFalse(read_variable_paths(Reader(), current))
        self.assertEqual(current.one('Components/Component[1]/LibPath_Variable').values, ('',))
        self.assertEqual(current.one('Components/Component[1]/Pattern/Model3D/Model3DFile_Variable').values, ('',))
        self.assertEqual(current.one('CacheLib/Slots/Slot/VariablePath').values, ('',))
        self.assertEqual(current.one('ProjectDir').values, ('',))

    def test_inactive_project_lists_and_empty_cache_slots_are_not_expanded(self):
        current = board()
        current.one('ProjectLibs_Type').set_values(0)
        empty = current.one('CacheLib/Slots').add('Slot', 18, 'unused.lib')
        read_variable_paths(SimpleNamespace(header=SimpleNamespace(version=52)), current)
        self.assertIsNone(current.one('ProjectLibs_Folders/Folder').child('VariablePath'))
        self.assertIsNone(current.one('ProjectLibs_Libs/Lib').child('VariablePath'))
        self.assertIsNone(empty.child('VariablePath'))


if __name__ == '__main__':
    unittest.main()
