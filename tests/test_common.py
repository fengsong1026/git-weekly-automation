"""Tests for scripts/common.py — shared utilities."""

import json
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from common import (
    load_config,
    resolve_api_key,
    get_git_user_email,
    validate_iso_week,
    purge_old_data,
)


class TestLoadConfig(unittest.TestCase):
    """Test config.json loading."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        # Override CONFIG_FILE location
        import common
        self._orig_config = common.CONFIG_FILE
        common.CONFIG_FILE = Path(self.tmpdir.name) / "config.json"

    def tearDown(self):
        import common
        common.CONFIG_FILE = self._orig_config
        self.tmpdir.cleanup()

    def test_load_config_missing_file(self):
        """Returns empty dict when config.json doesn't exist."""
        cfg = load_config()
        self.assertEqual(cfg, {})

    def test_load_config_valid(self):
        """Returns parsed dict when config.json is valid."""
        (Path(self.tmpdir.name) / "config.json").write_text(
            json.dumps({"api_key": "sk-test", "api_base": "https://x.com/v1"})
        )
        cfg = load_config()
        self.assertEqual(cfg["api_key"], "sk-test")
        self.assertEqual(cfg["api_base"], "https://x.com/v1")

    def test_load_config_corrupt(self):
        """Returns empty dict on corrupt JSON."""
        (Path(self.tmpdir.name) / "config.json").write_text("not valid json {{{")
        cfg = load_config()
        self.assertEqual(cfg, {})

    def test_resolve_api_key_env(self):
        """Resolves from env var first."""
        os.environ["OPENAI_API_KEY"] = "env-key"
        (Path(self.tmpdir.name) / "config.json").write_text(
            json.dumps({"api_key": "config-key"})
        )
        key = resolve_api_key()
        self.assertEqual(key, "env-key")
        del os.environ["OPENAI_API_KEY"]

    def test_resolve_api_key_config(self):
        """Falls back to config when no env var."""
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]
        (Path(self.tmpdir.name) / "config.json").write_text(
            json.dumps({"api_key": "config-key"})
        )
        key = resolve_api_key()
        self.assertEqual(key, "config-key")


class TestGitUserEmail(unittest.TestCase):
    """Test git user email detection (relies on git being installed)."""

    def test_returns_string(self):
        """Returns a string (may be empty if git not configured)."""
        email = get_git_user_email()
        self.assertIsInstance(email, str)


class TestValidateIsoWeek(unittest.TestCase):
    """Test ISO week number validation."""

    def test_valid_weeks(self):
        """Weeks 1-53 are valid."""
        for w in [1, 25, 52, 53]:
            self.assertEqual(validate_iso_week(w), w)

    def test_invalid_too_low(self):
        """Week 0 exits."""
        with self.assertRaises(SystemExit):
            validate_iso_week(0)

    def test_invalid_too_high(self):
        """Week 54 exits."""
        with self.assertRaises(SystemExit):
            validate_iso_week(54)

    def test_invalid_negative(self):
        """Negative weeks exit."""
        with self.assertRaises(SystemExit):
            validate_iso_week(-1)


class TestPurgeOldData(unittest.TestCase):
    """Test data retention cleanup."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        import common
        self._orig_project = common.PROJECT_DIR
        common.PROJECT_DIR = Path(self.tmpdir.name)
        # Create directories
        (common.PROJECT_DIR / "data" / "commits").mkdir(parents=True)
        (common.PROJECT_DIR / "data" / "logs").mkdir(parents=True)
        (common.PROJECT_DIR / "reports").mkdir(parents=True)

        # Create old files (mtime = 100 weeks ago)
        old_time = (datetime.now() - timedelta(weeks=100)).timestamp()
        (common.PROJECT_DIR / "data" / "commits" / "old.jsonl").write_text("{}")
        os.utime(common.PROJECT_DIR / "data" / "commits" / "old.jsonl", (old_time, old_time))
        (common.PROJECT_DIR / "reports" / "old.md").write_text("# old")
        os.utime(common.PROJECT_DIR / "reports" / "old.md", (old_time, old_time))
        (common.PROJECT_DIR / "data" / "logs" / "old.log").write_text("log")
        os.utime(common.PROJECT_DIR / "data" / "logs" / "old.log", (old_time, old_time))

        # Create recent files
        (common.PROJECT_DIR / "data" / "commits" / "recent.jsonl").write_text("{}")
        (common.PROJECT_DIR / "reports" / "recent.md").write_text("# recent")
        (common.PROJECT_DIR / "data" / "logs" / "recent.log").write_text("log")

    def tearDown(self):
        import common
        common.PROJECT_DIR = self._orig_project
        self.tmpdir.cleanup()

    def test_purge_removes_old_files(self):
        """Old files beyond retention are deleted."""
        deleted = purge_old_data({
            "cleanup": {
                "commits_weeks": 52,
                "reports_weeks": 26,
                "logs_days": 90,
            }
        })
        self.assertEqual(deleted["commits"], 1)
        self.assertEqual(deleted["reports"], 1)
        self.assertEqual(deleted["logs"], 1)

    def test_purge_keeps_recent_files(self):
        """Recent files within retention are kept."""
        import common
        old_commit = common.PROJECT_DIR / "data" / "commits" / "old.jsonl"
        recent_commit = common.PROJECT_DIR / "data" / "commits" / "recent.jsonl"

        deleted = purge_old_data({
            "cleanup": {"commits_weeks": 52, "reports_weeks": 0, "logs_days": 0}
        })
        self.assertFalse(old_commit.exists())
        self.assertTrue(recent_commit.exists())

    def test_purge_zero_retention_disables(self):
        """Setting retention to 0 disables purging for that category."""
        import common
        old_report = common.PROJECT_DIR / "reports" / "old.md"
        deleted = purge_old_data({
            "cleanup": {"commits_weeks": 0, "reports_weeks": 0, "logs_days": 0}
        })
        self.assertEqual(deleted["commits"], 0)
        self.assertEqual(deleted["reports"], 0)
        self.assertEqual(deleted["logs"], 0)
        self.assertTrue(old_report.exists())

    def test_purge_no_config(self):
        """Works with default retention values when no config provided."""
        deleted = purge_old_data({})
        self.assertGreaterEqual(deleted["commits"], 0)


if __name__ == "__main__":
    unittest.main()
