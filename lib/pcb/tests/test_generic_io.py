"""PCB integration through generic content recognition and conversion APIs."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import lib
import lib.pcb
from lib.common import asc
from lib.pcb.formats import io
from lib.pcb.formats.errors import PcbError
from lib.pcb.formats.export_context import ExportContext
from lib.pcb.formats.import_context import ImportContext
from lib.pcb.model.objects import new_document
from lib.pcb.tests.test_dip_output import configured_document


class GenericPcbIoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.design = configured_document()
        cls.buffers = {key: io.serialize(cls.design, format=key, report=lib.ConversionReport())
                       for key in ('dip', 'asc', 'dipxml')}

    def setUp(self):
        selected = patch.dict(lib._FAMILY_ADAPTERS, pcb=io)
        selected.start()
        self.addCleanup(selected.stop)

    def assert_model(self, document):
        self.assertEqual(document.representation, 'pcb')
        self.assertEqual(lib.document_family(document), 'pcb')
        expected, actual = self.design.one('/Board'), document.one('/Board')
        for path, field in (('Components/Component', 'RefDes'), ('Nets/Net', 'Name')):
            self.assertEqual(actual.one(path)[field], expected.one(path)[field])
        document.validate()

    def test_all_buffers_and_family_entry_points_use_one_editable_model(self):
        for format, data in self.buffers.items():
            with self.subTest(format=format):
                document = lib.parse(data, report=lib.ConversionReport())
                self.assert_model(document)
                self.assert_model(lib.pcb.parse(data, report=lib.ConversionReport()))
                self.assertIs(lib.format_capabilities(format, family='pcb'), io.format_capabilities(format))
                for target in self.buffers:
                    saved = lib.serialize(document, format=target, report=lib.ConversionReport())
                    self.assert_model(lib.parse(saved, report=lib.ConversionReport()))

    def test_generic_file_reads_use_one_buffer_and_ignore_misleading_suffix(self):
        path = Path('supplied.xml')
        for format, data in self.buffers.items():
            with self.subTest(format=format):
                with patch.object(Path, 'read_bytes', autospec=True, return_value=data) as reader:
                    document = lib.read(path, report=lib.ConversionReport())
                reader.assert_called_once_with(path)
                self.assert_model(document)

    def test_generic_file_output_matches_buffer_and_preserves_source(self):
        before = asc.dumps(self.design, preserve=False)
        with TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            for format in self.buffers:
                path = Path(temporary)/('output.'+format)
                with self.subTest(format=format):
                    lib.write(self.design, path, report=lib.ConversionReport())
                    self.assertEqual(path.read_bytes(), self.buffers[format])
                    self.assert_model(lib.read(path, report=lib.ConversionReport()))
        self.assertEqual(asc.dumps(self.design, preserve=False), before)

    def test_contexts_are_owned_by_the_selected_family(self):
        context = ImportContext(background_color=None)
        for data in self.buffers.values():
            self.assert_model(lib.parse(data, context=context, report=lib.ConversionReport()))
        with self.assertRaisesRegex(TypeError, 'PCB input context'):
            lib.parse(self.buffers['dip'], context=lib.ImportContext(), report=lib.ConversionReport())
        exported = lib.serialize(new_document(), format='dip', context=ExportContext(units='inch'),
                                 report=lib.ConversionReport())
        self.assertEqual(lib.parse(exported, report=lib.ConversionReport()).root['Units'], 'inch')
        with self.assertRaises(TypeError):
            lib.serialize(self.design, format='dip', context=lib.ExportContext(), report=lib.ConversionReport())

    def test_reports_accumulate_file_and_buffer_failures_without_duplicates(self):
        report = lib.ConversionReport()
        with patch.object(Path, 'read_bytes', return_value=self.buffers['dip']):
            with self.assertRaises(TypeError):
                lib.read('input.xml', context={}, report=report, label='input')
        with self.assertRaises(lib.UnsupportedFileError) as stopped:
            lib.serialize(self.design, format='dip', version=999, report=report, label='output')
        self.assertEqual((stopped.exception.family, stopped.exception.version, stopped.exception.reason),
                         ('pcb', 999, 'version'))
        self.assertEqual([(n.operation, n.format, n.file, n.label) for n in report.errors],
                         [('import', 'dip', 'input.xml', 'input'), ('export', 'dip', None, 'output')])

    def test_bad_output_version_does_not_replace_an_existing_file(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            path = Path(temporary)/'existing.dip'
            path.write_bytes(b'existing')
            with self.assertRaises(lib.UnsupportedFileError):
                lib.write(self.design, path, version=999, report=lib.ConversionReport())
            self.assertEqual(path.read_bytes(), b'existing')

    def test_text_source_views_require_explicit_conversion(self):
        for format in ('asc', 'dipxml'):
            with self.subTest(format=format):
                source = lib.parse_source(self.buffers[format], report=lib.ConversionReport())
                self.assertEqual(source.representation, format)
                if format == 'asc':
                    before = asc.dumps(source)
                else:
                    from lib.pcb.formats.dipxml.syntax import dumps
                    before = dumps(source)
                self.assert_model(source.as_pcb(report=lib.ConversionReport()))
                self.assertEqual(asc.dumps(source) if format == 'asc' else dumps(source), before)
                with self.assertRaisesRegex(PcbError, 'editable model'):
                    lib.serialize(source, format='dip', report=lib.ConversionReport())
                with patch.object(Path, 'read_bytes', return_value=self.buffers[format]) as reader:
                    inspected = lib.read_source('source.data', report=lib.ConversionReport())
                reader.assert_called_once()
                self.assertEqual(inspected.representation, format)

    def test_binary_source_view_already_uses_the_editable_model(self):
        self.assert_model(lib.parse_source(self.buffers['dip'], report=lib.ConversionReport()))

    def test_future_source_dialects_remain_inspectable_but_cannot_be_imported(self):
        sources = ('(Source "DipTrace-PCBN" 999)',
                   '<Source Type="DipTrace-PCB" Version="99.0"/>')
        for text in sources:
            with self.subTest(text=text):
                source = lib.parse_source(text, report=lib.ConversionReport())
                with self.assertRaises(lib.UnsupportedFileError) as stopped:
                    source.as_pcb(report=lib.ConversionReport())
                self.assertEqual(stopped.exception.reason, 'version')

    def test_existing_model_conversion_clones_relationships(self):
        copied = self.design.as_pcb(report=lib.ConversionReport())
        self.assertIsNot(copied, self.design)
        self.assert_model(copied)
        self.assertTrue(list(copied.references))
        for reference in copied.references:
            self.assertIs(reference.source._owner(), copied)
            self.assertIs(reference.target._owner(), copied)


if __name__ == '__main__':
    unittest.main()
