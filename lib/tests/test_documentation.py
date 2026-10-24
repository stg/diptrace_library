"""Execute the introduction and each independent API-reference example."""
from contextlib import redirect_stdout
from io import StringIO
import os
from pathlib import Path
import re
import tempfile
import unittest

from lib import (
    ConversionReport, Document, new_net, new_pin, new_schematic, new_symbol,
    parse, read, serialize,
)


def fixture(reference):
    design = new_schematic(sheet_name="Example")
    part = design.one("/Schematic/Components").append(new_symbol("Connector", reference))
    part["Value"] = "Signal input"
    part["X"], part["Y"] = 15, 30
    pin = part.child("Pins").append(new_pin())
    pin["Number"], pin["StringNumber"] = 1, "1"
    net = design.one("/Schematic/Nets").append(new_net("SIGNAL"))
    pin["Net"] = net
    return {"design": design, "part": part, "pin": pin, "net": net}


class DocumentationTests(unittest.TestCase):
    def _blocks(self, name):
        guide = Path(__file__).resolve().parents[2] / "doc" / name
        text = guide.read_text(encoding="utf-8")
        matches = list(re.finditer(r"```python\n(.*?)```", text, re.DOTALL))
        self.assertTrue(matches, f"{name} must contain executable examples")
        for match in matches:
            # Preserve guide line numbers in tracebacks.
            prefix = "\n" * text.count("\n", 0, match.start(1))
            yield match[1], compile(prefix + match[1], str(guide), "exec")

    def test_documentation_examples(self):
        original_directory = Path.cwd()
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            try:
                os.chdir(temporary)
                self._getting_started()
                self._api_reference()
            finally:
                os.chdir(original_directory)

    def _getting_started(self):
        inputs = fixture("J1")
        original = serialize(inputs["design"], format="dch")
        Path("design.dch").write_bytes(original)
        namespace = {"__name__": "__documentation__"}
        with redirect_stdout(StringIO()):
            for _, code in self._blocks("GETTING_STARTED.md"):
                exec(code, namespace)
        self.assertEqual(Path("design.dch").read_bytes(), original)
        for name in ("edited.dch", "edited.dchxml", "in_mils.dchxml"):
            loaded = read(name, report=ConversionReport())
            part = loaded.one('/Schematic/Components/Part[RefDes="J1"]')
            self.assertEqual(part["Value"], "Sensor input")
            self.assertEqual(part["X"], 15)

    def _api_reference(self):
        baseline = fixture("R1")["design"]
        buffers = {
            format: serialize(baseline, format=format)
            for format in ("dch", "asc", "dchxml")
        }
        for number, (_, code) in enumerate(self._blocks("API.md"), 1):
            # Each entry starts fresh: reference examples must not depend on
            # imports, edits or variables from an earlier reference entry.
            namespace = {"__name__": "__documentation__", **fixture("R1")}
            with self.subTest(reference_example=number):
                with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
                    parent = Path.cwd()
                    try:
                        os.chdir(directory)
                        for format, data in buffers.items():
                            Path("design." + format).write_bytes(data)
                        with redirect_stdout(StringIO()):
                            exec(code, namespace)
                        design = namespace["design"]
                        self.assertIsInstance(design, Document)
                        design.validate()
                        for path in Path.cwd().iterdir():
                            if path.stem == "design" or path.suffix not in (".dch", ".asc", ".dchxml"):
                                continue
                            output = parse(path.read_bytes(), format=path.suffix, report=ConversionReport())
                            output.validate()
                            expected = design.one("/Schematic/Components/Part")["Value"]
                            actual = output.one("/Schematic/Components/Part")["Value"]
                            self.assertEqual(actual, expected)
                    finally:
                        os.chdir(parent)


if __name__ == "__main__":
    unittest.main()
