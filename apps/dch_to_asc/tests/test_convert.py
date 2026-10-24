"""The command works with standard defaults and preserves files on failure."""
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from lib import new_schematic, parse_asc
from apps.dch_to_asc.convert import convert


class ConvertTests(unittest.TestCase):
    def test_cli_needs_no_context_file(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            source, target = Path(folder)/'input.dch', Path(folder)/'output.asc'
            data = new_schematic().to_dch_bytes()
            source.write_bytes(data)
            result = subprocess.run([sys.executable, str(ROOT/'apps/dch_to_asc/convert.py'), str(source), str(target)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(parse_asc(target.read_text()).one('/Units').values, ('mm',))
            self.assertEqual(source.read_bytes(), data)

    def test_failed_conversion_keeps_existing_output(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            source, target = Path(folder)/'input.dch', Path(folder)/'output.asc'
            source.write_bytes(b'invalid input')
            target.write_bytes(b'existing output')
            with self.assertRaises(ValueError):
                convert(source, target)
            self.assertEqual(target.read_bytes(), b'existing output')


if __name__ == '__main__':
    unittest.main()
