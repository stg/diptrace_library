"""The converter uses detected PCB data and its family's optional context."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from lib import ConversionReport, read, serialize
from lib.pcb import ExportContext
from lib.pcb.tests.test_dip_output import configured_document
from apps.common.components import physical_components
from apps.diptrace_convert.context import load_context
from apps.diptrace_convert.convert import convert, main


class PcbConverterTests(unittest.TestCase):
    def test_all_nine_pcb_conversions_need_no_context(self):
        document = configured_document()
        with TemporaryDirectory() as folder:
            root = Path(folder)
            for source_format in ('dip', 'asc', 'dipxml'):
                source = root/('input.'+source_format)
                source.write_bytes(serialize(document, format=source_format, report=ConversionReport()))
                for target_format in ('dip', 'asc', 'dipxml'):
                    with self.subTest(source=source_format, target=target_format):
                        target = root/(source_format+'.'+target_format)
                        convert(source, target, report=ConversionReport())
                        rebuilt = read(target, report=ConversionReport())
                        self.assertEqual(rebuilt.representation, 'pcb')
                        self.assertEqual(rebuilt.one('/Board/Components/Component')['RefDes'],
                                         document.one('/Board/Components/Component')['RefDes'])

    def test_cli_uses_pcb_context_for_asc_and_xml_outputs(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source = root/'input.dip'
            source.write_bytes(serialize(configured_document(), format='dip', report=ConversionReport()))
            settings = root/'settings.json'
            settings.write_text(json.dumps({'units': 'mil'}), encoding='utf-8')
            for target_format in ('asc', 'dipxml'):
                target = root/('output.'+target_format)
                with self.subTest(format=target_format), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    self.assertEqual(main([str(source), str(target), '--context', str(settings)]), 0)
                self.assertEqual(read(target, report=ConversionReport()).root['Units'], 'mil')

    def test_context_loader_has_no_implicit_family_and_keeps_no_config_optional(self):
        self.assertIsNone(load_context(format='dip', family='pcb'))
        with TemporaryDirectory() as folder:
            path = Path(folder)/'settings.json'
            path.write_text('{"units": "inch"}', encoding='utf-8')
            self.assertIsInstance(load_context(path, format='dipxml', family='pcb'), ExportContext)
            path.write_text('{"line_widths": {"1": 0.3}}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'schematic ASC'):
                load_context(path, format='asc', family='pcb')

    def test_schematic_only_component_tools_reject_other_families(self):
        with self.assertRaisesRegex(ValueError, 'schematic'):
            list(physical_components(configured_document()))


if __name__ == '__main__':
    unittest.main()
