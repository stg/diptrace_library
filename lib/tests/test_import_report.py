"""One diagnostics contract spans import, inspection and export boundaries."""
from pathlib import Path
import tempfile
import unittest
import warnings

from lib import (ConversionReport, ExportReport, ImportReport,
                        ConversionWarning, parse, parse_source, parse_dch, read, write)
from lib.tests.test_route_import import source, encode, PATH
from lib.schematic.model.refs import (bind_schematic_references)


class ImportReportTests(unittest.TestCase):
    def test_each_adapter_collects_modernization_without_emitting_warnings(self):
        original = source()
        for format in ('dch','asc','dchxml'):
            with self.subTest(format=format):
                report = ConversionReport()
                with warnings.catch_warnings(record=True) as emitted:
                    warnings.simplefilter('always')
                    current = parse(encode(original,format),format=format,report=report)
                self.assertEqual(current.representation,'schematic')
                self.assertEqual(emitted,[])
                self.assertEqual(report.warnings,[])
                self.assertEqual(report.errors,[])
                self.assertIn('route-modernization',{n.rule for n in report.infos})
                self.assertTrue(all(n.operation=='import' and n.format==format for n in report.notices))

    def test_unresolved_attachments_collect_structured_warnings_and_keep_data(self):
        original = source()
        line = original.one(PATH)
        line.set_field('ConnectMode1',0)
        line.set_field('Connect1',99)
        line.set_field('ConnectL1',0)
        bind_schematic_references(original)
        for format in ('dch','asc'):
            report = ImportReport()
            current = parse(encode(original,format),format=format,report=report)
            self.assertTrue(current.references.issues)
            self.assertEqual(current.one(PATH).scalar('Connect1'),99)
            self.assertTrue(report.warnings)
            self.assertEqual(report.errors,[])
            self.assertTrue(any(n.paths for n in report.warnings if n.rule=='unresolved-reference'))
            self.assertEqual(sum(n.rule=='route-normalization-deferred' for n in report.warnings),1)

    def test_default_modernization_is_quiet_and_default_uncertainty_warns(self):
        original = source()
        with warnings.catch_warnings(record=True) as emitted:
            warnings.simplefilter('always')
            parse(encode(original,'dch'),format='dch')
        self.assertEqual(emitted,[])
        line = original.one(PATH)
        line.set_field('ConnectMode1',0)
        line.set_field('Connect1',99)
        line.set_field('ConnectL1',0)
        bind_schematic_references(original)
        with warnings.catch_warnings(record=True) as emitted:
            warnings.simplefilter('always')
            parse(encode(original,'dch'),format='dch')
        self.assertTrue(emitted)
        self.assertTrue(all(isinstance(item.message,ConversionWarning) for item in emitted))
        self.assertTrue(all(item.message.notice.operation=='import' for item in emitted))

    def test_errors_are_recorded_once_and_original_exceptions_still_raise(self):
        for format,data in (('dch',b'invalid'),('asc',b'('),('dchxml',b'<Source>')):
            report = ConversionReport()
            with self.subTest(format=format),self.assertRaises(Exception):
                parse(data,format=format,report=report)
            self.assertEqual(len(report.errors),1)
            self.assertEqual(report.errors[0].operation,'import')
            self.assertEqual(report.errors[0].format,format)
        # A failed session cannot capture a subsequent independent import.
        before = list(report.notices)
        parse(encode(source(),'dch'),format='dch',report=ConversionReport())
        self.assertEqual(report.notices,before)

    def test_read_direct_binary_and_source_conversion_use_the_same_report(self):
        original = source()
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            path = Path(temporary)/'design.dch'
            path.write_bytes(encode(original,'dch'))
            report = ImportReport()
            current = read(path=path,report=report)
            self.assertEqual(current.representation,'schematic')
            self.assertTrue(report.infos)
            self.assertTrue(all(n.format=='dch' for n in report.notices))
            missing = Path(temporary)/'missing.dch'
            failed = ImportReport()
            with self.assertRaises(FileNotFoundError):
                read(missing,report=failed)
            self.assertEqual(len(failed.errors),1)
        report = ImportReport()
        parse_dch(encode(original,'dch'),report=report)
        self.assertTrue(report.infos)
        report = ImportReport()
        parse_source(encode(original,'asc'),format='asc').as_schematic(report=report)
        self.assertTrue(report.infos)
        self.assertTrue(all(n.format=='asc' for n in report.notices))

    def test_one_report_can_cover_both_directions_and_aliases_are_compatible(self):
        self.assertIs(ConversionReport,ImportReport)
        self.assertIs(ConversionReport,ExportReport)
        report = ConversionReport()
        current = parse(encode(source(),'dch'),format='dch',report=report)
        with self.assertRaises(ValueError):
            current.to_dch_bytes(version=999,report=report)
        self.assertTrue(report.infos)
        self.assertEqual(report.errors[-1].operation,'export')
        self.assertEqual(report.errors[-1].format,'dch')
        self.assertTrue(all(n.operation=='import' for n in report.infos))
        with self.assertRaisesRegex(TypeError,'ConversionReport'):
            parse(b'',format='dch',report=[])

    def test_reusing_a_report_preserves_each_operation_and_exports_public_names(self):
        import lib as design
        self.assertTrue({'ConversionReport','ImportReport','ExportReport'} <= set(design.__all__))
        report=ConversionReport()
        data=encode(source(),'dch')
        parse(data,format='dch',report=report)
        initial=list(report.infos)
        self.assertTrue(initial)
        parse(data,format='dch',report=report)
        self.assertEqual(report.infos,initial+initial)

    def test_clear_resets_a_report_for_reuse_after_failure(self):
        report = ConversionReport()
        notices = report.notices
        data = encode(source(), 'dch')
        parse(data, format='dch', report=report, label='before reset')
        with self.assertRaises(Exception):
            parse(b'invalid', format='dch', report=report, label='failed')
        self.assertTrue(report.infos)
        self.assertTrue(report.errors)

        self.assertIsNone(report.clear())
        self.assertIs(report.notices, notices)
        self.assertEqual(report.notices, [])
        self.assertEqual((report.infos, report.warnings, report.errors), ([], [], []))
        parse(data, format='dch', report=report, label='after reset')
        self.assertTrue(report.infos)
        self.assertTrue(all(n.label == 'after reset' for n in report.notices))
        self.assertEqual(report.errors, [])

    def test_export_io_failures_share_the_report_contract_and_keep_exception_types(self):
        original=source()
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            for format in ('dch','asc','dchxml'):
                report=ConversionReport()
                with self.subTest(format=format),self.assertRaises(FileNotFoundError):
                    write(document=original,path=Path(temporary)/'missing'/('design.'+format),report=report)
                self.assertEqual(len(report.errors),1)
                self.assertEqual(report.errors[0].operation,'export')
                self.assertEqual(report.errors[0].format,format)

    def test_unknown_writer_is_reported_at_the_public_conversion_boundary(self):
        report=ConversionReport()
        with self.assertRaises(ValueError):
            write(source(),'design.unknown',report=report)
        self.assertEqual(len(report.errors),1)
        self.assertEqual(report.errors[0].operation,'export')
        self.assertEqual(report.errors[0].format,'unknown')


if __name__=='__main__':
    unittest.main()
