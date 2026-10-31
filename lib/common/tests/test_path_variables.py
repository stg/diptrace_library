"""Caller-supplied resource aliases are deterministic across document families."""
import unittest

from lib.common.path_variables import PathVariables
from lib.common.text.case import lowercase


class PathVariableTests(unittest.TestCase):
    def test_existing_public_configuration_is_the_shared_type(self):
        from lib import PathVariables as public
        from lib.schematic.formats.path_variables import PathVariables as schematic
        self.assertIs(public, PathVariables)
        self.assertIs(schematic, PathVariables)

    def test_builtin_project_and_custom_paths_do_not_change_actual_values(self):
        choices = PathVariables(main_dir='C:/Application',
                               custom=(('parts', 'D:/Parts', True),))
        self.assertEqual(choices.select('', 'C:/Application/Lib/parts.eli'),
                         '%maindir%/Lib/parts.eli')
        self.assertEqual(choices.select('', 'D:/Project/layout.dip', project_dir='D:/Project'),
                         '%projectdir%/layout.dip')
        self.assertEqual(choices.select('', 'D:/Parts/device.eli'), '%parts%/device.eli')
        self.assertEqual(choices.select('', 'D:/Project/layout.dip', project_dir='D:/Project',
                                        include_project=False), 'D:/Project/layout.dip')

    def test_compatible_existing_expressions_and_disabled_variables_remain(self):
        choices = PathVariables(main_dir='C:/Application',
                               custom=(('saved', 'D:/Parts', False),))
        self.assertEqual(choices.select('%maindir%/x', 'C:/Application/x'), '%maindir%/x')
        self.assertEqual(choices.select('%saved%/x', 'D:/Parts/x'), '%saved%/x')
        self.assertEqual(choices.select('%unavailable%/x', ''), '%unavailable%/x')
        self.assertEqual(choices.select('', 'D:/Parts/x'), 'D:/Parts/x')

    def test_custom_expansion_can_use_another_alias_and_detects_cycles(self):
        choices = PathVariables(main_dir='C:/Application',
                               custom=(('parts', '%maindir%/parts', True),))
        self.assertEqual(choices.select('', 'C:/Application/parts/x'), '%parts%/x')
        cyclic = PathVariables(custom=(('a', '%b%', True), ('b', '%a%', True)))
        with self.assertRaisesRegex(ValueError, 'cyclic'):
            cyclic.select('%a%/x', 'unchanged')

    def test_case_mappings_do_not_expand_characters_and_suffixes_need_a_separator(self):
        self.assertEqual(lowercase('İΩ'), 'İω')
        choices = PathVariables(main_dir='C:/Application')
        self.assertEqual(choices.select('', 'c:/application/x'), '%maindir%/x')
        self.assertEqual(choices.select('', 'C:/Application-extra/x'), 'C:/Application-extra/x')

    def test_invalid_configuration_is_rejected(self):
        for kwargs in ({'main_dir': 5}, {'standardlibs': 1}, {'custom': [('a', 'x')]}):
            with self.subTest(kwargs=kwargs), self.assertRaises(TypeError):
                PathVariables(**kwargs)
        with self.assertRaises(TypeError):
            PathVariables().select(None, 'x')


if __name__ == '__main__':
    unittest.main()
