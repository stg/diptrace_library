"""Default output follows user folders without writing outside the test workspace."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from apps.diptrace_db.paths import default_database_path


class DefaultPathTests(unittest.TestCase):
    def test_windows_uses_the_resolved_documents_folder(self):
        documents = Path(__file__).parent.resolve() / "redirected-documents"
        with patch("apps.diptrace_db.paths.sys.platform", "win32"):
            with patch("apps.diptrace_db.paths._windows_documents", return_value=documents):
                self.assertEqual(
                    default_database_path(),
                    documents / "DipTraceLibrary" / "component_db.json",
                )

    def test_macos_uses_documents_under_home(self):
        home = Path(__file__).parent.resolve() / "home"
        with patch("apps.diptrace_db.paths.sys.platform", "darwin"):
            with patch("apps.diptrace_db.paths.Path.home", return_value=home):
                self.assertEqual(
                    default_database_path(),
                    home / "Documents" / "DipTraceLibrary" / "component_db.json",
                )

    def test_linux_respects_configured_documents_with_spaces(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            home = Path(folder).resolve()
            config = home / "config"
            config.mkdir()
            (config / "user-dirs.dirs").write_text(
                'XDG_DOCUMENTS_DIR="$HOME/Design Documents"\n', encoding="utf-8",
            )
            with patch("apps.diptrace_db.paths.sys.platform", "linux"):
                with patch("apps.diptrace_db.paths.Path.home", return_value=home):
                    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config)}):
                        self.assertEqual(
                            default_database_path(),
                            home / "Design Documents" / "DipTraceLibrary" / "component_db.json",
                        )

    def test_linux_without_user_directory_settings_uses_documents(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as folder:
            home = Path(folder).resolve()
            with patch("apps.diptrace_db.paths.sys.platform", "linux"):
                with patch("apps.diptrace_db.paths.Path.home", return_value=home):
                    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(home / "config")}):
                        self.assertEqual(
                            default_database_path(),
                            home / "Documents" / "DipTraceLibrary" / "component_db.json",
                        )
