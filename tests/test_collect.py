"""Tests for scripts/collect-commits — repo discovery, hash loading, commit dedup."""

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

cc = SourceFileLoader("cc", str(SCRIPTS_DIR / "collect-commits")).load_module()
_is_git_repo = cc._is_git_repo
load_existing_hashes = cc.load_existing_hashes
load_all_existing_hashes = cc.load_all_existing_hashes
append_commits_to_files = cc.append_commits_to_files


class TestIsGitRepo(unittest.TestCase):
    """Test detection of git repositories."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_dot_git_directory(self):
        """A dir with .git/ directory is a git repo."""
        (self.root / "repo" / ".git").mkdir(parents=True)
        self.assertTrue(_is_git_repo(self.root / "repo"))

    def test_dot_git_file(self):
        """A dir with .git file (submodule) is a git repo."""
        repo = self.root / "submodule"
        repo.mkdir()
        (repo / ".git").write_text("gitdir: ../.git/modules/sub")
        self.assertTrue(_is_git_repo(repo))

    def test_no_git(self):
        """A plain directory is not a git repo."""
        (self.root / "plain").mkdir()
        self.assertFalse(_is_git_repo(self.root / "plain"))

    def test_non_existent(self):
        """A non-existent path returns False (no crash)."""
        self.assertFalse(_is_git_repo(self.root / "nope"))


class TestHashLoading(unittest.TestCase):
    """Test loading commit hashes from JSONL files."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.file = Path(self.tmpdir.name) / "test.jsonl"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_empty_file(self):
        """Empty file returns empty set."""
        self.file.write_text("")
        hashes = load_existing_hashes(self.file)
        self.assertEqual(hashes, set())

    def test_missing_file(self):
        """Missing file returns empty set."""
        hashes = load_existing_hashes(self.file)
        self.assertEqual(hashes, set())

    def test_valid_entries(self):
        """Hashes are extracted from valid JSONL lines."""
        self.file.write_text(
            json.dumps({"hash": "abc123"}) + "\n"
            + json.dumps({"hash": "def456"}) + "\n"
        )
        hashes = load_existing_hashes(self.file)
        self.assertIn("abc123", hashes)
        self.assertIn("def456", hashes)
        self.assertEqual(len(hashes), 2)

    def test_skips_corrupt_lines(self):
        """Invalid JSON lines are skipped, valid ones still loaded."""
        self.file.write_text(
            "not json\n"
            + json.dumps({"hash": "good"}) + "\n"
            + "also bad\n"
        )
        hashes = load_existing_hashes(self.file)
        self.assertIn("good", hashes)
        self.assertEqual(len(hashes), 1)

    def test_skips_missing_hash(self):
        """Entries without a 'hash' key are skipped."""
        self.file.write_text(
            json.dumps({"author": "test"}) + "\n"
            + json.dumps({"hash": "valid"}) + "\n"
        )
        hashes = load_existing_hashes(self.file)
        self.assertIn("valid", hashes)
        self.assertNotIn("", hashes)
        self.assertEqual(len(hashes), 1)


class TestLoadAllHashes(unittest.TestCase):
    """Test loading all hashes from data/commits/ directory."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self._orig_data = cc.DATA_DIR
        cc.DATA_DIR = Path(self.tmpdir.name)

    def tearDown(self):
        cc.DATA_DIR = self._orig_data
        self.tmpdir.cleanup()

    def test_loads_across_multiple_files(self):
        """Hashes are aggregated across all JSONL files."""
        f1 = Path(self.tmpdir.name) / "2026-W01.jsonl"
        f2 = Path(self.tmpdir.name) / "2026-W02.jsonl"
        f1.write_text(json.dumps({"hash": "aaa"}) + "\n")
        f2.write_text(json.dumps({"hash": "bbb"}) + "\n")

        hashes = load_all_existing_hashes()
        self.assertIn("aaa", hashes)
        self.assertIn("bbb", hashes)
        self.assertEqual(len(hashes), 2)

    def test_empty_directory(self):
        """Empty data dir returns empty set."""
        hashes = load_all_existing_hashes()
        self.assertEqual(hashes, set())


class TestAppendCommitsToFiles(unittest.TestCase):
    """Test appending commits to weekly JSONL files with dedup."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self._orig_data = cc.DATA_DIR
        cc.DATA_DIR = Path(self.tmpdir.name)

    def tearDown(self):
        cc.DATA_DIR = self._orig_data
        self.tmpdir.cleanup()

    def test_writes_commits_to_correct_week(self):
        """Commits are written to the correct ISO week file."""
        commits = [
            {
                "hash": "abc",
                "author": "test",
                "email": "t@t.com",
                "timestamp": "2026-06-15T10:00:00+00:00",
                "message": "commit 1",
                "repo": "test",
                "repo_path": "/tmp/test",
                "branch": "main",
                "hostname": "test",
            }
        ]
        import datetime
        dt = datetime.datetime.fromisoformat("2026-06-15T10:00:00+00:00")
        iso_year, iso_week, _ = dt.isocalendar()
        expected_file = f"{iso_year}-W{iso_week:02d}"

        counts = append_commits_to_files(commits)
        self.assertIn(expected_file, counts)
        self.assertEqual(counts[expected_file], 1)

        # Verify file content
        week_file = cc.DATA_DIR / f"{expected_file}.jsonl"
        self.assertTrue(week_file.exists())
        content = week_file.read_text()
        data = json.loads(content.strip())
        self.assertEqual(data["hash"], "abc")

    def test_deduplicates_existing_hashes(self):
        """Writing the same hash twice only writes once."""
        commit = {
            "hash": "dedup-test",
            "author": "x", "email": "x@x", "timestamp": "2026-06-15T10:00:00+00:00",
            "message": "x", "repo": "x", "repo_path": "/tmp/x",
            "branch": "main", "hostname": "x",
        }
        # Write once
        counts1 = append_commits_to_files([commit])
        # Write again — should be deduped
        counts2 = append_commits_to_files([commit])

        total_writes = sum(counts1.values()) + sum(counts2.values())
        self.assertEqual(total_writes, 1)  # Only first write succeeded


if __name__ == "__main__":
    unittest.main()
