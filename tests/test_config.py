from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ti_oracle_data.config import PROJECT_ROOT, Settings


class SettingsTest(unittest.TestCase):
    def test_default_database_is_independent_of_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {}, clear=True), patch("os.getcwd", return_value=directory):
                settings = Settings.from_env()
        self.assertEqual(settings.database_path, PROJECT_ROOT / "data/ti_oracle.sqlite3")

    def test_explicit_database_path_is_preserved(self) -> None:
        with patch.dict(os.environ, {"TI_ORACLE_DATABASE": "./custom.sqlite3"}, clear=True):
            settings = Settings.from_env()
        self.assertEqual(settings.database_path, Path("./custom.sqlite3"))


if __name__ == "__main__":
    unittest.main()
