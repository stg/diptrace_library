"""Usage links, incremental reads and CLI defaults are the database contract."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from lib import new_schematic, new_symbol
from apps.diptrace_db.build_db import build_db, main, read_components
from apps.diptrace_db.database import assemble_database, cached_files


def save_design(path, value="10k"):
    document = new_schematic()
    part = document.one("/Schematic/Components").append(new_symbol("RES", "R1"))
    part["Value"] = value
    part.child("Pattern")["Name"] = "RES_0603"
    path.write_bytes(document.to_dch_bytes())
    return document


class DatabaseTests(unittest.TestCase):
    def test_extraction_preserves_authored_identity_and_excludes_logical_parts(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path = Path(folder) / "input.dch"
            document = save_design(path)
            parts = document.one("/Schematic/Components")
            logical = parts.append(new_symbol("Port", "PORT1"))
            logical["PartType"] = 2
            disabled = parts.append(new_symbol("Unused", "R99"))
            disabled["Enabled"] = False
            path.write_bytes(document.to_dch_bytes())

            result = read_components(path)

            self.assertEqual(result.components, {("RES", "10k", "RES_0603")})

    def test_output_contains_only_links_root_and_reuse_metadata(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root = Path(folder).resolve()
            save_design(root / "first.dch")
            save_design(root / "second.DCH")
            (root / "empty.dch").write_bytes(new_schematic().to_dch_bytes())

            result = build_db(root)
            database = assemble_database(root, result.files)

            self.assertEqual(set(database), {"version", "root", "files", "components"})
            self.assertEqual(database["components"], [{
                "name": "RES", "value": "10k", "pattern": "RES_0603",
                "files": ["first.dch", "second.DCH"],
            }])
            self.assertEqual(set(database["files"]["first.dch"]), {"mtime_ns", "size_bytes"})
            self.assertIn("empty.dch", database["files"])
            self.assertEqual(database["root"], str(root))

    def test_unchanged_files_are_not_imported_and_changed_files_replace_links(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root = Path(folder).resolve()
            first, second = root / "first.dch", root / "second.dch"
            save_design(first)
            save_design(second)
            previous = assemble_database(root, build_db(root).files)

            with patch("apps.diptrace_db.build_db.read_components", wraps=read_components) as reader:
                unchanged = build_db(root, previous=previous)
                reader.assert_not_called()
            self.assertEqual(unchanged.reused_count, 2)

            # Set the timestamp explicitly so the test needs no timing sleeps.
            before = second.stat()
            save_design(second, value="22k")
            os.utime(second, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
            with patch("apps.diptrace_db.build_db.read_components", wraps=read_components) as reader:
                updated = build_db(root, previous=previous)
                reader.assert_called_once_with(second)
            database = assemble_database(root, updated.files)
            self.assertEqual(updated.reused_count, 1)
            self.assertEqual(
                [(entry["value"], entry["files"]) for entry in database["components"]],
                [("10k", ["first.dch"]), ("22k", ["second.dch"])],
            )

    def test_deleted_files_disappear_and_failures_are_retried(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root = Path(folder).resolve()
            good, bad = root / "good.dch", root / "bad.dch"
            save_design(good)
            bad.write_bytes(b"invalid design")
            first = build_db(root)
            previous = assemble_database(root, first.files)
            self.assertEqual(len(first.failures), 1)
            self.assertNotIn("bad.dch", previous["files"])

            good.unlink()
            with patch("apps.diptrace_db.build_db.read_components", wraps=read_components) as reader:
                second = build_db(root, previous=previous)
                reader.assert_called_once_with(bad)
            self.assertEqual(assemble_database(root, second.files)["components"], [])
            self.assertEqual(len(second.failures), 1)

    def test_old_or_incomplete_caches_trigger_a_real_read(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root = Path(folder).resolve()
            source = root / "input.dch"
            save_design(source)
            database = assemble_database(root, build_db(root).files)
            broken = json.loads(json.dumps(database))
            broken["components"][0]["files"] = ["missing.dch"]
            old = {"extraction_format": 1, "root": str(root)}
            for previous in (old, broken):
                with self.subTest(previous=previous):
                    self.assertEqual(cached_files(previous, root), {})
                    with patch("apps.diptrace_db.build_db.read_components", wraps=read_components) as reader:
                        build_db(root, previous=previous)
                        reader.assert_called_once_with(source)

    def test_parallel_and_serial_scans_produce_the_same_database(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root = Path(folder).resolve()
            save_design(root / "first.dch")
            save_design(root / "second.dch", value="22k")
            (root / "bad.dch").write_bytes(b"invalid design")
            serial = build_db(root)
            parallel = build_db(root, workers=2)
            self.assertEqual(
                assemble_database(root, serial.files),
                assemble_database(root, parallel.files),
            )
            self.assertEqual(len(parallel.failures), 1)

    def test_first_run_requires_root_and_announces_default_output(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            output = Path(folder) / "Documents" / "component_db.json"
            messages, errors = io.StringIO(), io.StringIO()
            with patch("apps.diptrace_db.build_db.default_database_path", return_value=output):
                with redirect_stdout(messages), redirect_stderr(errors):
                    with self.assertRaises(SystemExit) as stopped:
                        main([])
            self.assertEqual(stopped.exception.code, 2)
            self.assertIn(f"Using default output at {output}", messages.getvalue())
            self.assertIn("supply --root", errors.getvalue())
            self.assertFalse(output.exists())

    def test_rerun_uses_saved_root_and_skips_unchanged_imports(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root = Path(folder) / "inputs"
            root.mkdir()
            save_design(root / "input.dch")
            output = Path(folder) / "Documents" / "component_db.json"
            with patch("apps.diptrace_db.build_db.default_database_path", return_value=output):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(main(["--root", str(root)]), 0)
                original = output.read_bytes()
                with redirect_stdout(io.StringIO()):
                    with patch("apps.diptrace_db.build_db.read_components") as reader:
                        self.assertEqual(main([]), 0)
                        reader.assert_not_called()
                self.assertEqual(output.read_bytes(), original)

    def test_missing_saved_root_has_actionable_error_and_preserves_database(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root = Path(folder) / "removed"
            output = Path(folder) / "database.json"
            original = json.dumps({"version": 2, "root": str(root)})
            output.write_text(original)
            errors = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(errors):
                with self.assertRaises(SystemExit) as stopped:
                    main(["--out", str(output)])
            self.assertEqual(stopped.exception.code, 2)
            self.assertIn("does not exist", errors.getvalue())
            self.assertIn("--root", errors.getvalue())
            self.assertNotIn("Traceback", errors.getvalue())
            self.assertEqual(output.read_text(), original)

    def test_explicit_output_and_new_root_override_saved_choices(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            first, second = Path(folder) / "first", Path(folder) / "second"
            first.mkdir()
            second.mkdir()
            save_design(first / "one.dch")
            save_design(second / "two.dch", value="22k")
            output = Path(folder) / "database.json"
            with patch("apps.diptrace_db.build_db.default_database_path", side_effect=AssertionError):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(main(["--root", str(first), "--out", str(output)]), 0)
                    self.assertEqual(main(["--root", str(second), "--out", str(output)]), 0)
            database = json.loads(output.read_text())
            self.assertEqual(database["root"], str(second.resolve()))
            self.assertEqual(set(database["files"]), {"two.dch"})

    def test_cli_reports_partial_failure_without_storing_run_statistics(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root = Path(folder) / "inputs"
            root.mkdir()
            save_design(root / "good.dch")
            (root / "bad.dch").write_bytes(b"invalid design")
            output = Path(folder) / "database.json"
            errors = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(errors):
                status = main(["--root", str(root), "--out", str(output)])
            self.assertEqual(status, 1)
            self.assertIn("Skipped", errors.getvalue())
            self.assertIn("bad.dch", errors.getvalue())
            self.assertNotIn("failures", json.loads(output.read_text()))

    def test_cli_rejects_invalid_worker_count_before_resolving_output(self):
        with patch("apps.diptrace_db.build_db.default_database_path") as default_path:
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stopped:
                main(["--workers", "0"])
        self.assertEqual(stopped.exception.code, 2)
        default_path.assert_not_called()

    def test_output_failure_has_processing_status_and_readable_error(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root = Path(folder) / "inputs"
            root.mkdir()
            output = Path(folder) / "database.json"
            output.write_text("existing database")
            errors = io.StringIO()
            with patch.object(Path, "write_text", side_effect=OSError("destination unavailable")):
                with redirect_stdout(io.StringIO()), redirect_stderr(errors):
                    status = main(["--root", str(root), "--out", str(output)])
            self.assertEqual(status, 1)
            self.assertIn("Error: database build failed", errors.getvalue())
            self.assertNotIn("Traceback", errors.getvalue())
            self.assertEqual(output.read_text(), "existing database")


if __name__ == "__main__":
    unittest.main()
