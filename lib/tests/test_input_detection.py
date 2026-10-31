"""Input declarations select adapters independently of the supplied filename."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import lib
from lib.tests.test_document_families import FAMILIES
from lib.tests.test_route_import import encode, source


class InputDetectionTests(unittest.TestCase):
    def setUp(self):
        # Test unavailable-family behavior explicitly as implementations grow.
        selected = patch.dict(lib._FAMILY_ADAPTERS,
                              {'schematic': lib._FAMILY_ADAPTERS['schematic']}, clear=True)
        selected.start()
        self.addCleanup(selected.stop)

    def test_files_use_content_before_known_unknown_or_missing_extensions(self):
        document = lib.new_schematic()
        with TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            for format in ('dch', 'asc', 'dchxml'):
                data = lib.serialize(document, format=format)
                for suffix in ('.xml', '.dch', '.asc', '.unknown', ''):
                    path = Path(temporary) / ('design' + suffix)
                    path.write_bytes(data)
                    with self.subTest(format=format, suffix=suffix):
                        with patch.object(Path, 'read_bytes', autospec=True,
                                          return_value=data) as reader:
                            current = lib.read(path)
                        reader.assert_called_once_with(path)
                        self.assertEqual(current.representation, 'schematic')
                        self.assertEqual(lib.serialize(current, format=format), data)
                        inspected = lib.read_source(path)
                        self.assertEqual(inspected.representation,
                                         'schematic' if format == 'dch' else format)

    def test_buffers_detect_format_without_a_filename(self):
        document = lib.new_schematic()
        for format in ('dch', 'asc', 'dchxml'):
            data = lib.serialize(document, format=format)
            buffers = (data,) if format == 'dch' else (data, data.decode())
            for buffer in buffers:
                with self.subTest(format=format, buffer=type(buffer).__name__):
                    current = lib.parse(buffer)
                    self.assertEqual(lib.serialize(current, format=format), data)
                    inspected = lib.parse_source(buffer)
                    self.assertEqual(inspected.representation,
                                     'schematic' if format == 'dch' else format)

    def test_xml_declaration_bom_and_comments_do_not_select_another_format(self):
        xml = lib.serialize(lib.new_schematic(), format='dchxml').decode()
        for data in (xml.encode('utf-8-sig'),
                     xml.replace('encoding="utf-8"', 'encoding="utf-16"').encode('utf-16'),
                     '<!-- (Source "DipTrace-PCBN" 9) -->' + xml[xml.index('<Source'):]):
            with self.subTest(buffer=type(data).__name__):
                self.assertEqual(lib.document_family(lib.parse(data)), 'schematic')

    def test_unavailable_family_uses_detected_format_and_version_in_errors(self):
        for family, native, xml, signature, source_type, root, xml_type in FAMILIES:
            binary = bytes([len(signature)]) + signature.encode() + (1_000_007).to_bytes(3, 'big')
            for format, data, version in (
                (native, binary, 7),
                ('asc', f'(Source "{source_type}" 7)', 7),
                (xml, f'<{root} Type="{xml_type}" Version="5.3"/>', '5.3'),
            ):
                for operation in (lib.parse, lib.parse_source):
                    report = lib.ConversionReport()
                    with self.subTest(family=family, format=format,
                                      operation=operation.__name__):
                        with self.assertRaises(lib.UnsupportedFileError) as stopped:
                            operation(data, report=report)
                        error = stopped.exception
                        self.assertEqual((error.format, error.family, error.version, error.reason),
                                         (format, family, version, 'family'))
                        self.assertEqual(len(report.errors), 1)
                        self.assertEqual(report.errors[0].format, format)

    def test_explicit_format_and_family_remain_independent_overrides(self):
        xml = lib.serialize(lib.new_schematic(), format='dchxml')
        with TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            path = Path(temporary) / 'design.asc'
            path.write_bytes(xml)
            for operation, args in ((lib.parse_source, (xml,)), (lib.read_source, (path,))):
                with self.subTest(operation=operation.__name__):
                    with self.assertRaises(ValueError) as stopped:
                        operation(*args, format='asc')
                    self.assertNotIsInstance(stopped.exception, lib.UnsupportedFileError)
                    self.assertEqual(operation(*args, format='.DCHXML').representation, 'dchxml')
                    with self.assertRaises(lib.UnsupportedFileError) as stopped:
                        operation(*args, family='pcb')
                    self.assertEqual((stopped.exception.format, stopped.exception.family),
                                     ('dchxml', 'pcb'))
                    with self.assertRaises(lib.UnsupportedFileError) as stopped:
                        operation(*args, format='unknown')
                    self.assertEqual((stopped.exception.format, stopped.exception.family),
                                     ('unknown', 'schematic'))

    def test_partial_syntax_still_needs_explicit_selection(self):
        fragment = '(Label "inspect me")'
        with self.assertRaises(lib.UnsupportedFileError):
            lib.parse_source(fragment)
        with self.assertRaises(lib.UnsupportedFileError):
            lib.parse_source(fragment, format='asc')
        inspected = lib.parse_source(fragment, format='asc', family='schematic')
        self.assertEqual(inspected.one('/Label').values, ('inspect me',))
        with TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            path = Path(temporary) / 'fragment.asc'
            path.write_text(fragment)
            with self.assertRaises(lib.UnsupportedFileError):
                lib.read_source(path, family='schematic')
            inspected = lib.read_source(path, format='asc', family='schematic')
            self.assertEqual(inspected.one('/Label').values, ('inspect me',))

    def test_an_unrecognized_xml_root_does_not_borrow_a_nested_identity(self):
        data = '<Other><Source Type="DipTrace-Schematic" Version="5.3"/></Other>'
        with self.assertRaises(lib.UnsupportedFileError) as stopped:
            lib.parse(data)
        self.assertIsNone(stopped.exception.family)

    def test_unrecognized_files_do_not_select_a_parser_from_their_extension(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            for suffix in ('.dch', '.asc', '.dchxml', '.xml', '.unknown', ''):
                path = Path(temporary) / ('design' + suffix)
                path.write_bytes(b'unrecognized content')
                for operation in (lib.read, lib.read_source):
                    with self.subTest(suffix=suffix, operation=operation.__name__):
                        report = lib.ConversionReport()
                        with self.assertRaises(lib.UnsupportedFileError) as stopped:
                            operation(path, report=report)
                        self.assertIsNone(stopped.exception.format)
                        self.assertEqual(stopped.exception.reason, 'format')
                        self.assertEqual(len(report.errors), 1)
                        self.assertEqual(report.errors[0].format, 'unknown')

    def test_recognized_native_versions_reach_the_existing_version_gate(self):
        for data, version in ((b'\x07DTSCHEM' + (1_000_053).to_bytes(3, 'big'), 53),
                              (b'\x0bDTSCHEM2.21', 28)):
            with self.subTest(version=version):
                with self.assertRaises(lib.UnsupportedFileError) as stopped:
                    lib.parse(data)
                error = stopped.exception
                self.assertEqual((error.format, error.family, error.version, error.reason),
                                 ('dch', 'schematic', version, 'version'))

    def test_detected_format_attributes_notices_and_failures(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            path = Path(temporary) / 'design.xml'
            for format in ('dch', 'asc', 'dchxml'):
                data = encode(source(), format)
                path.write_bytes(data)
                for operation, args in ((lib.parse, (data,)), (lib.read, (path,))):
                    with self.subTest(format=format, operation=operation.__name__):
                        report = lib.ConversionReport()
                        operation(*args, report=report, label='detected')
                        self.assertTrue(report.infos)
                        self.assertTrue(all(notice.format == format and notice.label == 'detected'
                                            for notice in report.notices))
                        self.assertTrue(all(notice.file == (str(path) if operation is lib.read else None)
                                            for notice in report.notices))
            path.write_text('<Source Type="DipTrace-Schematic"><Broken></Source>')
            report = lib.ConversionReport()
            with self.assertRaises(ValueError):
                lib.read(path, report=report)
            self.assertEqual(len(report.errors), 1)
            self.assertEqual(report.errors[0].format, 'dchxml')

    def test_explicit_custom_handler_never_eagerly_reads_or_normalizes(self):
        document = lib.new_schematic()
        callback = Mock(return_value=document)
        with patch.dict(lib._READERS, custom=callback):
            with patch.object(Path, 'read_bytes', side_effect=AssertionError('unnecessary read')):
                for operation in (lib.read, lib.read_source):
                    self.assertIs(operation('design.xml', format='custom', option=1), document)
        self.assertEqual(callback.call_count, 2)
        callback.assert_called_with('design.xml', option=1)
