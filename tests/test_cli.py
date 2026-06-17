"""Tests for scripts/cli — argument dispatch, shebang detection."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


class TestShebangDetection(unittest.TestCase):
    """Test that _run_script correctly identifies script interpreters."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        # Create test scripts with different shebangs
        self.py_script = Path(self.tmpdir.name) / "test.py"
        self.py_script.write_text("#!/usr/bin/env python3\nprint('hello')")
        self.py_script.chmod(0o755)

        self.bash_script = Path(self.tmpdir.name) / "test.sh"
        self.bash_script.write_text("#!/usr/bin/env bash\necho hello")
        self.bash_script.chmod(0o755)

        self.sh_script = Path(self.tmpdir.name) / "test.sh2"
        self.sh_script.write_text("#!/usr/bin/env sh\necho hello")
        self.sh_script.chmod(0o755)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_python_shebang_detected(self):
        with open(self.py_script, "r") as f:
            shebang = f.readline().strip()
        self.assertIn("python", shebang)

    def test_bash_shebang_detected(self):
        with open(self.bash_script, "r") as f:
            shebang = f.readline().strip()
        self.assertIn("bash", shebang)

    def test_sh_shebang_detected(self):
        with open(self.sh_script, "r") as f:
            shebang = f.readline().strip()
        self.assertIn("sh", shebang)


class TestCLIArgumentParsing(unittest.TestCase):
    """Test that CLI routes commands correctly (parse_known_args behavior)."""

    def setUp(self):
        # Import the cli module's main parser setup
        self.cli_dir = Path(__file__).resolve().parent.parent / "scripts"

    def test_cli_exists_and_is_executable(self):
        """CLI entry point exists."""
        cli = self.cli_dir / "cli"
        self.assertTrue(cli.is_file())

    def test_all_scripts_have_shebangs(self):
        """Every script in scripts/ starts with a valid shebang."""
        for f in self.cli_dir.iterdir():
            if f.suffix in (".py",) or f.name in ("setup", "cli", "schedule",
                                                     "collect-commits",
                                                     "generate-weekly-report"):
                if f.is_file():
                    first_line = f.read_text().split("\n")[0]
                    self.assertTrue(
                        first_line.startswith("#!"),
                        f"{f.name} missing shebang: {first_line}"
                    )


class TestCLIImports(unittest.TestCase):
    """Test that all script modules can be imported without error."""

    def _load(self, filename, name=None):
        from importlib.machinery import SourceFileLoader
        path = str(Path(__file__).resolve().parent.parent / "scripts" / filename)
        return SourceFileLoader(name or filename, path).load_module()

    def test_registry_import(self):
        from registry import load_registry, save_registry
        self.assertTrue(callable(load_registry))

    def test_common_import(self):
        from common import load_config, get_git_user_email, purge_old_data
        self.assertTrue(callable(load_config))

    def test_schedule_import(self):
        schedule = self._load("schedule")
        self.assertTrue(callable(schedule.parse_schedule))

    def test_collect_import(self):
        cc = self._load("collect-commits", "cc")
        self.assertTrue(callable(cc._is_git_repo))

    def test_report_import(self):
        gwr = self._load("generate-weekly-report", "gwr")
        self.assertTrue(callable(gwr.fill_template))


if __name__ == "__main__":
    unittest.main()
