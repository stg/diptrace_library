"""Available families share dispatch without sharing contexts or model classes."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import lib
from lib.common import asc
from lib.common.conversion import import_notice


def adapter(family, native, xml, source_type):
    document = asc.loads(f'(Source "{source_type}" 7)')
    formats = {key: lib.FormatCapabilities(key, family, (7,), (7,), 7)
               for key in (native, xml, 'asc')}

    def capabilities(key):
        if key not in formats:
            raise lib.UnsupportedFileError(format=key, family=family)
        return formats[key]

    return SimpleNamespace(
        format_capabilities=capabilities, formats=formats, document=document,
        parse=Mock(return_value=document), parse_source=Mock(return_value=document),
        serialize=Mock(return_value=b'output'), write=Mock())


class FamilyDispatchTests(unittest.TestCase):
    def test_registered_family_uses_content_for_buffers_and_single_file_reads(self):
        families = (
            ('pcb', 'dip', 'dipxml', 'DipTrace-PCBN'),
            ('component', 'eli', 'elixml', 'DipTrace-ElementLibrary'),
            ('pattern', 'lib', 'libxml', 'DipTrace-ComLibrary'),
        )
        context = object()
        path = Path('misleading.xml')
        for family, native, xml, source_type in families:
            backend = adapter(family, native, xml, source_type)
            data = f'(Source "{source_type}" 7)'.encode()
            with self.subTest(family=family), patch.dict(lib._FAMILY_ADAPTERS, {family: backend}):
                self.assertIs(lib.parse(data, context=context), backend.document)
                backend.parse.assert_called_once_with(data, format='asc', context=context)
                backend.parse.reset_mock()
                with patch.object(Path, 'read_bytes', autospec=True, return_value=data) as reader:
                    self.assertIs(lib.read(path, context=context), backend.document)
                reader.assert_called_once_with(path)
                backend.parse.assert_called_once_with(data, format='asc', context=context, source=str(path))
                self.assertIs(lib.format_capabilities(native), backend.formats[native])
                self.assertIs(lib.format_capabilities('asc', family=family), backend.formats['asc'])

    def test_source_inspection_is_dispatched_without_implicit_normalization(self):
        backend = adapter('pcb', 'dip', 'dipxml', 'DipTrace-PCBN')
        data, path = b'(Source "DipTrace-PCBN" 7)', Path('source.data')
        with patch.dict(lib._FAMILY_ADAPTERS, pcb=backend):
            self.assertIs(lib.parse_source(data), backend.document)
            with patch.object(Path, 'read_bytes', return_value=data) as reader:
                self.assertIs(lib.read_source(path), backend.document)
            reader.assert_called_once()
        backend.parse.assert_not_called()
        self.assertEqual(backend.parse_source.call_count, 2)
        self.assertEqual(backend.parse_source.call_args.kwargs, {'format': 'asc', 'source': str(path)})

    def test_output_dispatch_uses_current_family_and_keeps_options(self):
        backend = adapter('pcb', 'dip', 'dipxml', 'DipTrace-PCBN')
        document, context, report = backend.document, object(), lib.ConversionReport()
        document.metadata.update(family='schematic', format='dch')
        with patch.dict(lib._FAMILY_ADAPTERS, pcb=backend):
            self.assertEqual(lib.serialize(document, format='.DIP', context=context, report=report,
                                           version=7), b'output')
            backend.serialize.assert_called_once_with(document, format='dip', context=context,
                                                       report=report, version=7)
            lib.write(document, 'output.dip', context=context, report=report, version=7)
            backend.write.assert_called_once_with(document, 'output.dip', format='dip',
                                                   context=context, report=report, version=7)
            with self.assertRaises(lib.UnsupportedFileError) as stopped:
                lib.serialize(document, format='asc', family='schematic')
            self.assertEqual((stopped.exception.family, stopped.exception.reason), ('pcb', 'family'))

    def test_explicit_family_can_select_an_adapter_for_unidentified_source(self):
        backend = adapter('pcb', 'dip', 'dipxml', 'DipTrace-PCBN')
        with patch.dict(lib._FAMILY_ADAPTERS, pcb=backend):
            self.assertIs(lib.parse_source('(Custom 1)', format='asc', family='PCB'), backend.document)
            backend.parse_source.assert_called_once_with('(Custom 1)', format='asc')

    def test_nested_import_notices_retain_detected_format_and_outer_attribution(self):
        backend = adapter('pcb', 'dip', 'dipxml', 'DipTrace-PCBN')

        def parse(data, **options):
            import_notice('info', 'example-import', 'Example normalization')
            return backend.document

        backend.parse.side_effect = parse
        report = lib.ConversionReport()
        with patch.dict(lib._FAMILY_ADAPTERS, pcb=backend):
            with patch.object(Path, 'read_bytes', return_value=b'(Source "DipTrace-PCBN" 7)'):
                lib.read('misleading.dch', report=report, label='file')
            lib.parse('(Source "DipTrace-PCBN" 7)', report=report, label='buffer')
        self.assertEqual([(n.operation, n.format, n.file, n.label) for n in report.notices],
                         [('import', 'asc', 'misleading.dch', 'file'),
                          ('import', 'asc', None, 'buffer')])

    def test_adapter_exception_is_preserved_and_reported_once(self):
        backend = adapter('pcb', 'dip', 'dipxml', 'DipTrace-PCBN')
        error = lib.UnsupportedFileError('future version', format='asc', family='pcb',
                                         version=8, reason='version')
        backend.parse.side_effect = error
        report = lib.ConversionReport()
        with patch.dict(lib._FAMILY_ADAPTERS, pcb=backend):
            with self.assertRaises(lib.UnsupportedFileError) as stopped:
                lib.parse('(Source "DipTrace-PCBN" 8)', report=report, label='future')
        self.assertIs(stopped.exception, error)
        self.assertEqual(len(report.errors), 1)
        self.assertEqual((report.errors[0].format, report.errors[0].label), ('asc', 'future'))

    def test_available_builtin_formats_cannot_be_shadowed_by_file_callbacks(self):
        backend = adapter('pcb', 'dip', 'dipxml', 'DipTrace-PCBN')
        with patch.dict(lib._FAMILY_ADAPTERS, pcb=backend):
            for register in (lib.register_reader, lib.register_writer):
                with self.subTest(register=register.__name__), self.assertRaisesRegex(ValueError, 'already registered'):
                    register('dip', Mock())

    def test_custom_file_callbacks_receive_their_own_context_without_an_eager_read(self):
        context, document = object(), asc.loads('(Custom 1)')
        reader, writer = Mock(return_value=document), Mock()
        with patch.dict(lib._READERS, custom=reader), patch.dict(lib._WRITERS, custom=writer):
            with patch.object(Path, 'read_bytes', side_effect=AssertionError('unnecessary read')):
                self.assertIs(lib.read('input.custom', context=context), document)
                lib.write(document, 'output.custom', context=context)
        reader.assert_called_once_with('input.custom', context=context)
        writer.assert_called_once_with(document, 'output.custom', context=context)


if __name__ == '__main__':
    unittest.main()
