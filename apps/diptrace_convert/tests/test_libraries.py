"""The converter follows each library adapter's formats and version types."""
from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from lib import ConversionReport
from apps.common.tests.library_cases import FAMILIES, registered, example
from apps.diptrace_convert.convert import convert, main


class LibraryConvertTests(unittest.TestCase):
    def test_all_nine_conversions_per_family_use_content_detection(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for family, native, xml in FAMILIES:
                with registered(family) as api:
                    for source_format in (native, 'asc', xml):
                        source = root / 'input.unknown'
                        source.write_bytes(api.serialize(example(family), format=source_format,
                                                         report=ConversionReport()))
                        before = source.read_bytes()
                        for target_format in (native, 'asc', xml):
                            with self.subTest(family=family, input=source_format, output=target_format):
                                target = root / ('output.' + target_format)
                                convert(source, target, report=ConversionReport())
                                rebuilt = api.read(target)
                                self.assertEqual(family, rebuilt.representation)
                                self.assertEqual('1', rebuilt.find_all('Pad')[0]['StringNumber'])
                                self.assertEqual(before, source.read_bytes())

    def test_cli_accepts_application_versions_and_rejects_unknown_versions_before_output(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for family, native, xml in FAMILIES:
                with self.subTest(family=family), registered(family) as api:
                    source, target = root / ('source.' + native), root / ('target.' + xml)
                    api.write(example(family), source)
                    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                        self.assertEqual(0, main([str(source), str(target), '--version', '5.3.5.1']))
                    self.assertIn(b'Version="5.3.5.1"', target.read_bytes())
                    before = target.read_bytes()
                    with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                        main([str(source), str(target), '--version', '99.1'])
                    self.assertEqual(2, raised.exception.code)
                    self.assertEqual(before, target.read_bytes())
