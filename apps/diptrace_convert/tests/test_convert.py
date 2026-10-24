"""Real conversions exercise format inference, version choices and file safety."""
from contextlib import redirect_stderr, redirect_stdout
import io
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from lib import ConversionReport, format_capabilities, new_schematic, new_symbol, read, serialize
from apps.diptrace_convert.convert import convert, main
from apps.diptrace_convert.context import load_context

REPOSITORY = Path(__file__).resolve().parents[3]


class ConvertTests(unittest.TestCase):
    def test_cli_needs_no_context_file(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            source = Path(folder) / "input.dch"
            target = Path(folder) / "output.asc"
            original = new_schematic().to_dch_bytes()
            source.write_bytes(original)
            result = subprocess.run(
                [sys.executable, "-m", "apps.diptrace_convert", str(source), str(target)],
                cwd=REPOSITORY, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(read(target).complete)
            self.assertEqual(source.read_bytes(), original)
            self.assertIn("Info: Wrote", result.stdout)

    def test_all_nine_format_combinations_preserve_authored_component_data(self):
        document = new_schematic()
        part = document.one("/Schematic/Components").append(new_symbol("Resistor", "R1"))
        part["Value"] = "10k"
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            for source_format in ("dch", "asc", "dchxml"):
                source = Path(folder) / ("input." + source_format.upper())
                original = serialize(document, format=source_format, report=ConversionReport())
                source.write_bytes(original)
                for target_format in ("dch", "asc", "dchxml"):
                    with self.subTest(source=source_format, target=target_format):
                        target = Path(folder) / ("nested/output." + target_format)
                        convert(source, target, report=ConversionReport())
                        restored = read(target)
                        component = restored.one('/Schematic/Components/Part[RefDes="R1"]')
                        self.assertEqual(component["Value"], "10k")
                        self.assertEqual(source.read_bytes(), original)

    def test_cli_uses_requested_versions_for_binary_and_xml(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            source = Path(folder) / "input.dch"
            source.write_bytes(new_schematic().to_dch_bytes())
            for format in ("dch", "dchxml"):
                version = max(format_capabilities(format).write_versions)
                target = Path(folder) / ("output." + format)
                with redirect_stdout(io.StringIO()):
                    status = main([str(source), str(target), "--version", str(version)])
                self.assertEqual(status, 0)
                expected = serialize(read(source), format=format, version=version)
                self.assertEqual(target.read_bytes(), expected)

    def test_unsupported_output_version_is_usage_error_and_keeps_existing_output(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            source, target = Path(folder) / "input.dch", Path(folder) / "output.asc"
            source.write_bytes(new_schematic().to_dch_bytes())
            target.write_bytes(b"existing output")
            errors = io.StringIO()
            with redirect_stderr(errors), self.assertRaises(SystemExit) as stopped:
                main([str(source), str(target), "--version", "999"])
            self.assertEqual(stopped.exception.code, 2)
            self.assertIn("cannot write version", errors.getvalue())
            self.assertEqual(target.read_bytes(), b"existing output")

    def test_unknown_extension_is_usage_error(self):
        errors = io.StringIO()
        with redirect_stderr(errors), self.assertRaises(SystemExit) as stopped:
            main(["input.dch", "output.unknown"])
        self.assertEqual(stopped.exception.code, 2)
        self.assertIn("no capabilities registered", errors.getvalue())

    def test_failed_conversion_keeps_existing_output_and_reports_one_error(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            source, target = Path(folder) / "input.dch", Path(folder) / "output.asc"
            source.write_bytes(b"invalid input")
            target.write_bytes(b"existing output")
            with self.assertRaises(ValueError):
                convert(source, target)
            errors = io.StringIO()
            with redirect_stderr(errors):
                status = main([str(source), str(target)])
            self.assertEqual(status, 1)
            self.assertEqual(errors.getvalue().count("Error:"), 1)
            self.assertNotIn("Traceback", errors.getvalue())
            self.assertEqual(target.read_bytes(), b"existing output")

    def test_cli_same_file_error_does_not_overwrite_input(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            source = Path(folder) / "input.dch"
            original = new_schematic().to_dch_bytes()
            source.write_bytes(original)
            errors = io.StringIO()
            with redirect_stderr(errors), self.assertRaises(SystemExit) as stopped:
                main([str(source), str(source)])
            self.assertEqual(stopped.exception.code, 2)
            self.assertIn("paths must differ", errors.getvalue())
            self.assertEqual(source.read_bytes(), original)

    def test_hard_link_cannot_be_used_to_overwrite_source(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            source, target = Path(folder) / "input.dch", Path(folder) / "output.dch"
            original = new_schematic().to_dch_bytes()
            source.write_bytes(original)
            os.link(source, target)
            with self.assertRaisesRegex(ValueError, "paths must differ"):
                convert(source, target)
            self.assertEqual(source.read_bytes(), original)

    def test_context_supports_common_and_destination_specific_overrides(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path = Path(folder) / "context.json"
            path.write_text('{"units": "mil"}')
            for format in ("dch", "asc", "dchxml"):
                context = load_context(path, format=format)
                self.assertEqual(context.units, "mil")
            path.write_text('{"active_sheet": 1}')
            self.assertEqual(load_context(path, format="dchxml").active_sheet, 1)
            with self.assertRaises(TypeError):
                load_context(path, format="asc")
            path.write_text('{"text_layout": {"unknown": 1}}')
            with self.assertRaisesRegex(ValueError, "unknown text layout"):
                load_context(path, format="asc")
            path.write_text('{"line_widths": {"1": 0.3}, "default_line_width": 0.2}')
            context = load_context(path, format="asc")
            self.assertEqual(context.line_width(1), 0.3)
            self.assertEqual(context.line_width(9), 0.2)

    def test_bad_context_is_usage_error_before_output_is_touched(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            source, target = Path(folder) / "input.dch", Path(folder) / "output.asc"
            source.write_bytes(new_schematic().to_dch_bytes())
            target.write_bytes(b"existing output")
            context = Path(folder) / "context.json"
            context.write_text('[1, 2]')
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stopped:
                main([str(source), str(target), "--context", str(context)])
            self.assertEqual(stopped.exception.code, 2)
            self.assertEqual(target.read_bytes(), b"existing output")


if __name__ == "__main__":
    unittest.main()
