"""Keep the public API walkthrough executable, including its semantic assertions."""
import os
from pathlib import Path
import re
import tempfile
import unittest


class DocumentationTests(unittest.TestCase):
    def test_api_walkthrough(self):
        repository = Path(__file__).resolve().parents[2]
        guide = repository / "doc" / "API.md"
        text = guide.read_text(encoding="utf-8")
        blocks = list(re.finditer(r"```python\n(.*?)```", text, re.DOTALL))
        self.assertTrue(blocks, "The API guide must contain runnable examples")
        namespace = {"__name__": "__documentation__"}
        original_directory = Path.cwd()
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            try:
                os.chdir(temporary)
                for number, match in enumerate(blocks, 1):
                    with self.subTest(example=number):
                        # Preserve guide line numbers in assertion tracebacks.
                        prefix = "\n" * text.count("\n", 0, match.start(1))
                        code = compile(prefix + match[1], str(guide), "exec")
                        exec(code, namespace)
            finally:
                os.chdir(original_directory)


if __name__ == "__main__":
    unittest.main()
