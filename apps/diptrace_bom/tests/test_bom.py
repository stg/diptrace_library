"""The BOM has identical component semantics across all supported inputs."""
import csv
from contextlib import redirect_stderr
import io
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from lib import ConversionReport, new_schematic, new_symbol
from apps.diptrace_bom.build_bom import build_bom, group_bom, main
from apps.common.components import Component

REPOSITORY = Path(__file__).resolve().parents[3]


def design():
    document = new_schematic()
    parts = document.one("/Schematic/Components")
    for reference, value, kind, enabled in (
        ("R10", "10k", 0, True),
        ("R2", "10k", 0, True),
        ("R2", "unused duplicate", 0, True),
        ("NET", "", 2, True),
        ("R99", "not populated", 0, False),
    ):
        part = parts.append(new_symbol("Resistor", reference))
        part["Value"] = value
        part["PartType"] = kind
        part["Enabled"] = enabled
        part.child("Pattern")["Name"] = "R_0603"
    return document


class BomTests(unittest.TestCase):
    def test_zero_padded_aliases_count_as_one_physical_component(self):
        rows = group_bom([
            Component('R003', 'Resistor', '10k', 'R_0603'),
            Component('R3', 'Resistor', '10k', 'R_0603'),
            Component('R4', 'Resistor', '10k', 'R_0603'),
        ])
        self.assertEqual(rows, [{
            'RefDes': 'R003, R4', 'Name': 'Resistor', 'Value': '10k', 'Pattern': 'R_0603',
        }])

    def test_bare_prefix_and_zero_count_as_one_component(self):
        rows = group_bom([
            Component('C', 'Capacitor', '10u', 'C_0603'),
            Component('C0', 'Capacitor', '10u', 'C_0603'),
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['RefDes'], 'C')

    def test_all_formats_group_physical_parts_in_natural_reference_order(self):
        document = design()
        expected = [{"RefDes": "R2, R10", "Name": "Resistor", "Value": "10k", "Pattern": "R_0603"}]
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            for suffix, emit in (
                (".dch", document.to_dch_bytes),
                (".asc", document.to_asc_bytes),
                (".dchxml", document.to_dchxml_bytes),
            ):
                with self.subTest(format=suffix):
                    path = Path(folder) / ("input" + suffix)
                    original = emit(report=ConversionReport())
                    path.write_bytes(original)

                    rows, complete = build_bom(path)

                    self.assertEqual(rows, expected)
                    self.assertTrue(complete)
                    self.assertEqual(path.read_bytes(), original)

    def test_csv_preserves_unicode_and_quoted_text(self):
        document = new_schematic()
        part = document.one("/Schematic/Components").append(new_symbol("Resistor", "R1"))
        part["Value"] = '10k\u00b5; "precision"'
        part.child("Pattern")["Name"] = "R_0603"
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            source = Path(folder) / "input.dch"
            output = Path(folder) / "bom.csv"
            source.write_bytes(document.to_dch_bytes())

            result = subprocess.run(
                [sys.executable, "-m", "apps.diptrace_bom.build_bom", str(source), str(output)],
                cwd=REPOSITORY, capture_output=True, text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            with output.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream, delimiter=";"))
            self.assertEqual(rows[0]["Value"], part["Value"])
            self.assertEqual(rows[0]["RefDes"], "R1")

    def test_invalid_input_leaves_existing_csv_untouched(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            source = Path(folder) / "input.dch"
            target = Path(folder) / "output.csv"
            source.write_bytes(b"invalid design")
            target.write_text("existing output")
            errors = io.StringIO()

            with redirect_stderr(errors):
                status = main([str(source), str(target)])

            self.assertEqual(status, 1)
            self.assertEqual(errors.getvalue().count("Error:"), 1)
            self.assertIn("BOM export failed", errors.getvalue())
            self.assertNotIn("Traceback", errors.getvalue())
            self.assertEqual(target.read_text(), "existing output")

    def test_input_and_output_cannot_be_the_same_file(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            source = Path(folder) / "input.dch"
            original = new_schematic().to_dch_bytes()
            source.write_bytes(original)
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main([str(source), str(source)])
            self.assertEqual(source.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
