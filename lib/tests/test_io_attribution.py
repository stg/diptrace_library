"""File and buffer I/O share diagnostics without retaining operation history."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from lib import ConversionReport, new_schematic, parse, read, serialize, write
from lib.tests.test_route_import import source, encode


class IoAttributionTests(unittest.TestCase):
    def test_custom_writer_failure_retains_exception_type_and_attribution(self):
        import lib as design
        def writer(document, path, **options):
            raise RuntimeError('writer service failed')
        report = ConversionReport()
        with patch.dict(design._WRITERS, {'custom': writer}):
            with self.assertRaisesRegex(RuntimeError, 'writer service failed'):
                write(new_schematic(), 'output.custom', report=report, label='custom')
        self.assertEqual(len(report.errors), 1)
        self.assertEqual(report.errors[0].file, 'output.custom')
        self.assertEqual(report.errors[0].label, 'custom')

    def test_shared_report_attributes_each_file_and_failure(self):
        report = ConversionReport()
        with TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            first = Path(temporary)/'first.dch'
            second = Path(temporary)/'second.asc'
            first.write_bytes(encode(source(), 'dch'))
            second.write_bytes(encode(source(), 'asc'))
            for path in (first, second):
                start = len(report.notices)
                design = read(path, report=report, label=path.stem)
                notices = report.notices[start:]
                self.assertTrue(notices)
                self.assertTrue(all(notice.file == str(path) and notice.label == path.stem
                                    for notice in notices))
            output = Path(temporary)/'missing'/'output.dch'
            with self.assertRaises(FileNotFoundError):
                write(design, output, report=report, label='output')
            self.assertEqual(report.errors[-1].file, str(output))
            self.assertEqual(report.errors[-1].label, 'output')
            self.assertEqual(report.errors[-1].operation, 'export')

    def test_buffer_labels_and_failure_do_not_leak_to_subsequent_operations(self):
        report = ConversionReport()
        design = parse(encode(source(), 'dch'), format='dch', report=report, label='buffer-a')
        self.assertTrue(report.infos)
        self.assertTrue(all(notice.file is None and notice.label == 'buffer-a' for notice in report.notices))
        with self.assertRaises(ValueError):
            serialize(design, format='dch', version=999, report=report, label='buffer-b')
        self.assertEqual(len(report.errors), 1)
        self.assertEqual(report.errors[0].label, 'buffer-b')
        self.assertIsNone(report.errors[0].file)
        start = len(report.notices)
        parse(encode(source(), 'dch'), format='dch', report=report)
        self.assertTrue(all(notice.file is None and notice.label is None for notice in report.notices[start:]))

    def test_file_and_buffer_outputs_are_equivalent_for_each_format(self):
        design = new_schematic()
        report = ConversionReport()
        with TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            for format in ('dch', 'asc', 'dchxml'):
                options = {'version': 52} if format != 'asc' else {}
                data = serialize(design, format=format, report=report, **options)
                self.assertIsInstance(data, bytes)
                path = Path(temporary)/('design.'+format)
                self.assertIsNone(write(design, path, report=report, **options))
                self.assertEqual(path.read_bytes(), data)
                parsed = parse(data, format=format, report=ConversionReport())
                loaded = read(path, report=ConversionReport())
                self.assertEqual(parsed.to_dch_bytes(version=52), loaded.to_dch_bytes(version=52))

    def test_clean_success_does_not_add_a_fake_history_entry(self):
        report = ConversionReport()
        serialize(new_schematic(), format='dch', report=report, label='clean')
        self.assertEqual(report.notices, [])

    def test_invalid_labels_are_rejected(self):
        with self.assertRaisesRegex(TypeError, 'label'):
            serialize(new_schematic(), format='dch', label=123)
