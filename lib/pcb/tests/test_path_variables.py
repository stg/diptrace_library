"""Explicit PCB aliases use the shared configuration on detached output views."""
from pathlib import Path
import unittest
from unittest.mock import patch

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.common.path_variables import PathVariables
from lib.pcb.formats.export_context import ExportContext
from lib.pcb.formats.export_view import prepare_export
from lib.pcb.formats.io import parse, serialize
from lib.pcb.tests.test_dip_output import configured_document
from lib.pcb.tests.test_dipxml_library import source as library_source


class PathVariableTests(unittest.TestCase):
    def test_context_is_shared_optional_and_resolves_destination_choices(self):
        document = configured_document()
        choices = PathVariables(main_dir='C:/Application')
        context = ExportContext(path_variables=choices)
        for format in ('dip', '.asc', 'DIPXML'):
            resolved = context.resolved(document, format=format)
            self.assertIsNot(resolved, context)
            self.assertIs(resolved.path_variables, choices)
        with self.assertRaisesRegex(ValueError, 'output format'):
            context.resolved(document, format='dch')
        with self.assertRaises(TypeError):
            ExportContext(path_variables={})

    def test_all_output_formats_use_current_paths_without_source_mutation_or_lookup(self):
        document = configured_document()
        board = document.one('/Board')
        board['ProjectDir'], board['RelSchem'] = 'D:/Project', 'D:/Project/design.dch'
        component = board.one('Components/Component')
        component['LibPath'], component['LibPath_Variable'] = 'D:/Parts/device.eli', ''
        model = component.one('Pattern/Model3D')
        model['Model3DFile'], model['Model3DFile_Variable'] = 'D:/Project/device.wrl', ''
        picture = board.one('Shapes/Shape[2]')
        picture['Picture_File'], picture['Picture_File_Variable'] = 'D:/Project/logo.bmp', ''
        before = dumps(document, preserve=False)
        context = ExportContext(path_variables=PathVariables(custom=(('parts', 'D:/Parts', True),)))
        expected = {
            'RelSchem_Variable': '%projectdir%/design.dch',
            'Components/Component/LibPath_Variable': '%parts%/device.eli',
            'Components/Component/Pattern/Model3D/Model3DFile_Variable': '%projectdir%/device.wrl',
            'Shapes/Shape[2]/Picture_File_Variable': '%projectdir%/logo.bmp',
        }
        for format in ('dip', 'asc', 'dipxml'):
            with self.subTest(format=format), patch.object(Path, 'read_bytes', side_effect=AssertionError('resource lookup')):
                output = serialize(document, format=format, context=context, report=ConversionReport())
                rebuilt = parse(output, report=ConversionReport())
                for path, value in expected.items():
                    self.assertEqual(rebuilt.one('/Board/'+path).values, (value,))
                self.assertEqual(rebuilt.one('/Board/Components/Component')['LibPath'], 'D:/Parts/device.eli')
                repeated = parse(serialize(rebuilt, format=format, context=context, report=ConversionReport()),
                                 report=ConversionReport())
                for path, value in expected.items():
                    self.assertEqual(repeated.one('/Board/'+path).values, (value,))
        self.assertEqual(dumps(document, preserve=False), before)

    def test_absent_context_retains_stored_variable_spellings(self):
        document = configured_document()
        board = document.one('/Board')
        board['RelSchem_Variable'] = '%unavailable%/schematic.dch'
        view, _ = prepare_export(document, report=ConversionReport())
        self.assertEqual(view.one('/Board')['RelSchem_Variable'], '%unavailable%/schematic.dch')

    def test_project_lists_and_cache_paths_share_choices_but_cached_models_are_independent(self):
        document = parse(library_source(), report=ConversionReport())
        board = document.one('/Board')
        board['ProjectLibs_Type'] = 2
        board.add('ProjectLibs_Folders').add('Folder', 'D:/Parts')
        board.add('ProjectLibs_Libs').add('Lib', 'D:/Parts/list.eli')
        slot = board.one('CacheLib/Slots/Slot')
        slot['LibPath'], slot['VariablePath'] = 'D:/Parts/cache.eli', ''
        model = slot.one('Definition/Pattern/Model3D')
        model['Model3DFile'] = 'D:/Parts/template.wrl'
        model['Model3DFile_Variable'] = '%saved%/template.wrl'
        context = ExportContext(path_variables=PathVariables(custom=(('parts', 'D:/Parts', True),)))
        before = dumps(document, preserve=False)
        for format in ('dip', 'asc', 'dipxml'):
            with self.subTest(format=format):
                rebuilt = parse(serialize(document, format=format, context=context, report=ConversionReport()),
                                report=ConversionReport())
                current = rebuilt.one('/Board')
                self.assertEqual(current.one('ProjectLibs_Folders/Folder')['VariablePath'], '%parts%')
                self.assertEqual(current.one('ProjectLibs_Libs/Lib')['VariablePath'], '%parts%/list.eli')
                cached = current.one('CacheLib/Slots/Slot')
                self.assertEqual(cached['VariablePath'], '%parts%/cache.eli')
                self.assertEqual(cached.one('Definition/Pattern/Model3D')['Model3DFile_Variable'],
                                 '%saved%/template.wrl')
        self.assertEqual(dumps(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
