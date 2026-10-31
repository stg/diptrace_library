"""Family-neutral dispatch and support errors preserve ordinary adapter failures."""
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import lib
from lib.common import asc
from lib.common.model import Document as CommonDocument
from lib.schematic.formats.dch.binary import UnsupportedVersionError


FAMILIES = (
    ('pcb', 'dip', 'dipxml', 'DTBOARD', 'DipTrace-PCBN', 'Source', 'DipTrace-PCB'),
    ('component', 'eli', 'elixml', 'DTELIB', 'DipTrace-ElementLibrary',
     'Library', 'DipTrace-ComponentLibrary'),
    ('pattern', 'lib', 'libxml', 'DTCLIB', 'DipTrace-ComLibrary',
     'Library', 'DipTrace-PatternLibrary'),
)


class DocumentFamilyTests(unittest.TestCase):
    def setUp(self):
        # Test unavailable-family behavior explicitly as implementations grow.
        selected = patch.dict(lib._FAMILY_ADAPTERS,
                              {'schematic': lib._FAMILY_ADAPTERS['schematic']}, clear=True)
        selected.start()
        self.addCleanup(selected.stop)

    def test_placeholders_expose_scoped_conversion_api_and_collect_failures(self):
        document = lib.new_schematic()
        for family, native, xml, *_ in FAMILIES:
            package = import_module('lib.' + family)
            for format in (native, xml, 'asc'):
                with self.subTest(family=family, format=format):
                    with self.assertRaises(lib.UnsupportedFileError) as stopped:
                        package.format_capabilities(format)
                    self.assertEqual((stopped.exception.family, stopped.exception.reason),
                                     (family, 'family'))
                    report = lib.ConversionReport()
                    with self.assertRaises(lib.UnsupportedFileError):
                        package.parse(b'', format=format, report=report, label='input')
                    self.assertEqual(len(report.errors), 1)
                    self.assertEqual((report.errors[0].operation, report.errors[0].format,
                                      report.errors[0].label), ('import', format, 'input'))
                    report.clear()
                    with self.assertRaises(lib.UnsupportedFileError):
                        package.serialize(document, format=format, report=report, label='output')
                    self.assertEqual(len(report.errors), 1)
                    self.assertEqual((report.errors[0].operation, report.errors[0].format,
                                      report.errors[0].label), ('export', format, 'output'))

    def test_asc_input_family_and_revision_come_from_source_declaration(self):
        for family, _, _, _, source_type, *_ in FAMILIES:
            text = ('(Note "(Source fake 1)")\n'
                    f'(Source "{source_type}" 7)\n')
            for data in (text, text.encode(), bytearray(text.encode()), memoryview(text.encode())):
                with self.subTest(family=family, buffer=type(data).__name__):
                    with self.assertRaises(lib.UnsupportedFileError) as stopped:
                        lib.parse(data, format='asc')
                    self.assertEqual((stopped.exception.format, stopped.exception.family,
                                      stopped.exception.version, stopped.exception.reason),
                                     ('asc', family, 7, 'family'))

    def test_native_and_xml_content_identify_unavailable_families(self):
        for family, native, xml, signature, _, root, source_type in FAMILIES:
            binary = bytes([len(signature)]) + signature.encode() + (1_000_007).to_bytes(3, 'big')
            markup = (f'<?xml version="1.0"?><!--source--><{root} Version="5.3" '
                      f'Type="{source_type}"/>')
            for format, data, version in ((native, binary, 7), (xml, markup, '5.3'),
                                           ('dch', binary, 7), ('dchxml', markup, '5.3')):
                with self.subTest(family=family, format=format):
                    with self.assertRaises(lib.UnsupportedFileError) as stopped:
                        lib.parse(data, format=format)
                    error = stopped.exception
                    self.assertEqual((error.family, error.version, error.reason),
                                     (family, version, 'family'))

    def test_unrecognized_input_and_unknown_format_share_the_support_error(self):
        for data, format in ((b'unrelated content', 'asc'), (b'', 'dch'),
                             ('(Source "Unknown" 7)', 'asc'),
                             (lib.serialize(lib.new_schematic(), format='asc'), 'unknown')):
            with self.subTest(format=format, data=data[:20]):
                with self.assertRaises(lib.UnsupportedFileError) as stopped:
                    lib.parse(data, format=format)
                self.assertEqual(str(stopped.exception), 'unsupported file format')
                self.assertEqual(stopped.exception.reason, 'format')

    def test_file_detection_uses_content_and_preserves_outputs_and_report_paths(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            path = Path(temporary) / 'design.asc'
            for family, _, _, _, source_type, *_ in FAMILIES:
                data = f'(Source "{source_type}" 7)'.encode()
                path.write_bytes(data)
                for operation in (lib.read, lib.read_source):
                    with self.subTest(family=family, operation=operation.__name__):
                        report = lib.ConversionReport()
                        with self.assertRaises(lib.UnsupportedFileError) as stopped:
                            operation(path, report=report, label='file')
                        self.assertEqual(stopped.exception.family, family)
                        self.assertEqual(len(report.errors), 1)
                        self.assertEqual((report.errors[0].file, report.errors[0].label),
                                         (str(path), 'file'))
                        self.assertEqual(path.read_bytes(), data)
                source = asc.loads(data.decode())
                with self.assertRaises(lib.UnsupportedFileError):
                    lib.write(source, path)
                self.assertEqual(path.read_bytes(), data)
            missing = Path(temporary) / 'missing.unknown'
            with self.assertRaises(FileNotFoundError):
                lib.read(missing)

    def test_output_family_comes_from_model_or_source_not_metadata_or_extension(self):
        for family, _, _, _, source_type, root, xml_type in FAMILIES:
            source = asc.loads(f'(Source "{source_type}" 7)')
            xml = CommonDocument(representation='xml')
            xml.root.add(root).add('Type', xml_type)
            for document in (source, xml):
                document.metadata.update(source_format='dch', family='schematic')
                with self.subTest(family=family, representation=document.representation):
                    self.assertEqual(lib.document_family(document), family)
                    with self.assertRaises(lib.UnsupportedFileError) as stopped:
                        lib.serialize(document, format='asc')
                    self.assertEqual((stopped.exception.family, stopped.exception.reason),
                                     (family, 'family'))
        document = lib.new_schematic()
        document.metadata.update(family='pcb', source_format='dip')
        self.assertEqual(lib.document_family(document), 'schematic')
        self.assertTrue(lib.serialize(document, format='asc'))
        with self.assertRaises(lib.UnsupportedFileError):
            lib.serialize(CommonDocument(), format='asc')

    def test_explicit_family_overrides_automatic_source_detection(self):
        source = '(Source "DipTrace-PCBN" 7)'
        with self.assertRaises(lib.UnsupportedFileError):
            lib.parse_source(source, format='asc')
        inspected = lib.parse_source(source, format='asc', family='SCHEMATIC')
        self.assertEqual(inspected.one('/Source').values, ('DipTrace-PCBN', 7))
        with self.assertRaises(lib.UnsupportedFileError) as stopped:
            lib.parse_source('(Source "DipTrace-Schematic" 46)', format='asc', family='pcb')
        self.assertEqual((stopped.exception.family, stopped.exception.version), ('pcb', 46))

    def test_unavailable_family_does_not_validate_schematic_context(self):
        data = b'(Source "DipTrace-PCBN" 7)'
        with TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            path = Path(temporary) / 'design.asc'
            path.write_bytes(data)
            for operation, args, options in ((lib.parse, (data,), {'format': 'asc'}),
                                              (lib.read, (path,), {})):
                with self.subTest(operation=operation.__name__):
                    with self.assertRaises(lib.UnsupportedFileError) as stopped:
                        operation(*args, context=object(), **options)
                    self.assertEqual(stopped.exception.family, 'pcb')

    def test_schematic_file_and_buffer_detection_remain_equivalent(self):
        document = lib.new_schematic()
        with TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            for format in ('dch', 'asc', 'dchxml'):
                with self.subTest(format=format):
                    data = lib.serialize(document, format=format)
                    self.assertEqual(lib.serialize(document, format=format, family='SCHEMATIC'), data)
                    restored = lib.parse(data, format=format)
                    self.assertEqual(lib.document_family(restored), 'schematic')
                    self.assertEqual(lib.serialize(restored, format=format), data)
                    path = Path(temporary) / ('design.' + format)
                    lib.write(document, path)
                    self.assertEqual(path.read_bytes(), data)
                    with patch.object(Path, 'read_bytes', autospec=True, return_value=data) as reader:
                        restored = lib.read(path)
                    reader.assert_called_once_with(path)
                    self.assertEqual(lib.serialize(restored, format=format), data)
                    source = lib.parse_source(data, format=format)
                    source.metadata.clear()
                    self.assertEqual(lib.document_family(source), 'schematic')

    def test_custom_file_registration_does_not_read_paths_or_inspect_documents(self):
        for format in ('custom', 'dip'):
            with self.subTest(format=format), patch.dict(lib._READERS), patch.dict(lib._WRITERS):
                document = lib.parse_asc('(Label "custom")')
                reader, writer = Mock(return_value=document), Mock()
                lib.register_reader('.' + format.upper(), reader)
                lib.register_writer(format, writer)
                path = 'missing.' + format
                with patch.object(Path, 'read_bytes', side_effect=AssertionError('unnecessary read')):
                    self.assertIs(lib.read(path, custom_option=1), document)
                    lib.write(document, path, custom_option=2)
                reader.assert_called_once_with(path, custom_option=1)
                writer.assert_called_once_with(document, path, custom_option=2)

    def test_asc_capabilities_require_family_and_unavailable_formats_report_metadata(self):
        with self.assertRaisesRegex(ValueError, 'explicit document family'):
            lib.format_capabilities('asc')
        self.assertEqual(lib.format_capabilities('asc', family='schematic').family, 'schematic')
        for family, native, xml, *_ in FAMILIES:
            for format in (native, xml):
                with self.subTest(format=format):
                    with self.assertRaises(lib.UnsupportedFileError) as stopped:
                        lib.format_capabilities('.' + format.upper())
                    self.assertEqual((stopped.exception.format, stopped.exception.family,
                                      stopped.exception.reason), (format, family, 'family'))

    def test_supported_adapter_parse_and_version_errors_are_not_masked(self):
        for data in ('(Source "DipTrace-Schematic" 46) (',
                     '<Source Type="DipTrace-Schematic"><Broken></Source>'):
            format = 'asc' if data.startswith('(') else 'dchxml'
            with self.subTest(format=format), self.assertRaises(ValueError) as stopped:
                lib.parse(data, format=format)
            self.assertNotIsInstance(stopped.exception, lib.UnsupportedFileError)
        for data, version in ((b'\x07DTSCHEM' + (1_000_053).to_bytes(3, 'big'), 53),
                              (b'\x0bDTSCHEM2.21', 28)):
            with self.subTest(version=version), self.assertRaises(UnsupportedVersionError) as stopped:
                lib.parse(data, format='dch')
            self.assertIsInstance(stopped.exception, lib.UnsupportedFileError)
            self.assertEqual((stopped.exception.format, stopped.exception.family,
                              stopped.exception.version, stopped.exception.reason),
                             ('dch', 'schematic', version, 'version'))

    def test_invalid_family_remains_a_configuration_error(self):
        with self.assertRaisesRegex(ValueError, 'unknown document family') as stopped:
            lib.parse(b'', format='asc', family='unknown')
        self.assertNotIsInstance(stopped.exception, lib.UnsupportedFileError)
