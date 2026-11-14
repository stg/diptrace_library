"""Standalone references retain syntax while using their actual unit policy."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from lib import ConversionReport
from lib.common.library_context import ExportContext
from apps.common.tests.library_cases import FAMILIES, registered, example
from apps.diptrace_check.check import check_file, main
from apps.diptrace_check.reference import Reference, source_document, source_rows, source_snapshot


class LibraryCheckTests(unittest.TestCase):
    def test_asc_references_allow_the_final_empty_expression_without_unit_headers(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for family, native, xml in FAMILIES:
                with self.subTest(family=family), registered(family) as api:
                    source, reference = root / ('source.' + native), root / 'reference.asc'
                    api.write(example(family), source)
                    api.write(api.read(source), reference)
                    self.assertTrue(reference.read_bytes().rstrip().endswith(b'()'))
                    before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in (source, reference)]
                    selected = Reference.load(reference, family=family)
                    self.assertIsNone(selected.units)
                    self.assertIsNone(selected.context(family))
                    raw = source_document(reference.read_bytes(), format='asc', family=family)
                    self.assertEqual(list(source_rows(raw)), sorted(source_snapshot(raw).items()))
                    result, report = check_file(source, formats=['asc'], references=[reference], cycles=2,
                                                report=ConversionReport())
                    comparison = result['results'][0]['references'][0]
                    self.assertEqual('clean', comparison['status'])
                    self.assertFalse(report.errors)
                    self.assertEqual(before, [(p.read_bytes(), p.stat().st_mtime_ns) for p in (source, reference)])

    def test_xml_references_retain_their_units_and_application_version(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for family, native, xml in FAMILIES:
                with self.subTest(family=family), registered(family) as api:
                    reference = root / ('reference.' + xml)
                    api.write(example(family), reference, context=ExportContext(units='inch'))
                    selected = Reference.load(reference, family=family)
                    self.assertEqual('5.3.5.1', selected.version)
                    self.assertEqual('inch', selected.context(family).units)

    def test_cli_accepts_an_xml_application_version(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for family, native, xml in FAMILIES:
                with self.subTest(family=family), registered(family) as api:
                    source, output = root / ('source.' + native), root / 'report.json'
                    api.write(example(family), source)
                    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                        self.assertEqual(0, main([str(source), '--format', xml, '--version', '5.3.5.1',
                                                  '--cycles', '2', '--json', str(output)]))
                    result = json.loads(output.read_text(encoding='utf-8'))
                    self.assertEqual('5.3.5.1', result['results'][0]['version'])
