"""Tests for scripts/registry.py — central registry CRUD, locking, orphan cleanup."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import registry as reg_mod


class TestRegistryCRUD(unittest.TestCase):
    """Test basic registry load/save/register/unregister operations."""

    def setUp(self):
        """Point registry at a temp file so tests don't touch the real registry."""
        self.tmpdir = tempfile.TemporaryDirectory()
        self._orig_registry_file = reg_mod.REGISTRY_FILE
        self._orig_registry_dir = reg_mod.REGISTRY_DIR
        reg_mod.REGISTRY_DIR = Path(self.tmpdir.name)
        reg_mod.REGISTRY_FILE = reg_mod.REGISTRY_DIR / "registry.json"
        # Also point lock file inside tmpdir
        reg_mod.LOCK_FILE = reg_mod.REGISTRY_DIR / ".registry.lock"

    def tearDown(self):
        reg_mod.REGISTRY_FILE = self._orig_registry_file
        reg_mod.REGISTRY_DIR = self._orig_registry_dir
        reg_mod.LOCK_FILE = self._orig_registry_dir / ".registry.lock"
        self.tmpdir.cleanup()

    def test_empty_registry(self):
        """Empty registry returns default structure."""
        reg = reg_mod.load_registry()
        self.assertEqual(reg["version"], 1)
        self.assertEqual(reg["installations"], {})

    def test_register_installation(self):
        """Registering an installation persists it."""
        reg_mod.register_installation(
            project_path="/tmp/test-project",
            install_method="manual",
            hooks_path_set=True,
            original_hooks_path="/old/hooks",
        )
        reg = reg_mod.load_registry()
        self.assertIn("/tmp/test-project", reg["installations"])
        entry = reg["installations"]["/tmp/test-project"]
        self.assertEqual(entry["install_method"], "manual")
        self.assertTrue(entry["hooks_path_set"])
        self.assertEqual(entry["original_hooks_path"], "/old/hooks")

    def test_unregister_installation(self):
        """Unregistering removes the entry."""
        reg_mod.register_installation(project_path="/tmp/to-remove")
        self.assertIn("/tmp/to-remove", reg_mod.load_registry()["installations"])
        reg_mod.unregister_installation("/tmp/to-remove")
        self.assertNotIn("/tmp/to-remove", reg_mod.load_registry()["installations"])

    def test_register_task_auto_creates_installation(self):
        """register_task creates installation entry if it doesn't exist."""
        reg_mod.register_task(
            project_path="/tmp/auto-create",
            task_name="test-task",
            label="com.test.task",
            plist_path="/tmp/test.plist",
            schedule="Mon 09:00",
            command="echo hi",
        )
        reg = reg_mod.load_registry()
        self.assertIn("/tmp/auto-create", reg["installations"])
        entry = reg["installations"]["/tmp/auto-create"]
        self.assertIn("test-task", entry["scheduled_tasks"])
        task = entry["scheduled_tasks"]["test-task"]
        self.assertEqual(task["label"], "com.test.task")
        self.assertEqual(task["schedule"], "Mon 09:00")
        self.assertEqual(task["command"], "echo hi")

    def test_unregister_task(self):
        """Unregistering a task removes it from the entry."""
        reg_mod.register_installation(project_path="/tmp/task-test")
        reg_mod.register_task(
            project_path="/tmp/task-test",
            task_name="rm-me",
            label="com.rm.me",
            plist_path="/tmp/rm.plist",
            schedule="daily 08:00",
            command="echo rm",
        )
        reg_mod.unregister_task("/tmp/task-test", "rm-me")
        reg = reg_mod.load_registry()
        # Entry should be gone because no hooks and no tasks remain
        self.assertNotIn("/tmp/task-test", reg["installations"])

    def test_clear_tasks(self):
        """Clearing all tasks from an installation."""
        reg_mod.register_installation(
            project_path="/tmp/clear-test",
            hooks_path_set=True,
            original_hooks_path="/foo",
        )
        reg_mod.register_task(
            project_path="/tmp/clear-test",
            task_name="t1", label="l1", plist_path="/tmp/p1",
            schedule="daily", command="c1",
        )
        reg_mod.register_task(
            project_path="/tmp/clear-test",
            task_name="t2", label="l2", plist_path="/tmp/p2",
            schedule="daily", command="c2",
        )
        self.assertEqual(
            len(reg_mod.load_registry()["installations"]["/tmp/clear-test"]["scheduled_tasks"]),
            2,
        )
        reg_mod.clear_tasks("/tmp/clear-test")
        entry = reg_mod.load_registry()["installations"]["/tmp/clear-test"]
        self.assertEqual(entry["scheduled_tasks"], {})

    def test_list_installations(self):
        """list_installations returns all registered entries."""
        reg_mod.register_installation(project_path="/tmp/a")
        reg_mod.register_installation(project_path="/tmp/b")
        installs = reg_mod.list_installations()
        self.assertIn("/tmp/a", installs)
        self.assertIn("/tmp/b", installs)

    def test_atomic_save(self):
        """Registry saves atomically (temp file + rename)."""
        reg_mod.register_installation(project_path="/tmp/atomic-test")
        self.assertTrue(reg_mod.REGISTRY_FILE.exists())
        # No .tmp files should linger
        tmp_files = list(reg_mod.REGISTRY_DIR.glob(".registry-*.tmp"))
        self.assertEqual(len(tmp_files), 0)


class TestOrphanCleanup(unittest.TestCase):
    """Test orphan detection and cleanup."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self._orig_registry_file = reg_mod.REGISTRY_FILE
        self._orig_registry_dir = reg_mod.REGISTRY_DIR
        reg_mod.REGISTRY_DIR = Path(self.tmpdir.name)
        reg_mod.REGISTRY_FILE = reg_mod.REGISTRY_DIR / "registry.json"
        reg_mod.LOCK_FILE = reg_mod.REGISTRY_DIR / ".registry.lock"

    def tearDown(self):
        reg_mod.REGISTRY_FILE = self._orig_registry_file
        reg_mod.REGISTRY_DIR = self._orig_registry_dir
        reg_mod.LOCK_FILE = self._orig_registry_dir / ".registry.lock"
        self.tmpdir.cleanup()

    def test_cleanup_orphans_removes_dead_paths(self):
        """Orphaned installations (dir doesn't exist) are cleaned up."""
        reg_mod.register_installation(
            project_path="/tmp/definitely-does-not-exist-xyz",
            install_method="manual",
            hooks_path_set=False,
        )
        cleaned = reg_mod.cleanup_orphans()
        self.assertIn("/tmp/definitely-does-not-exist-xyz", cleaned)
        reg = reg_mod.load_registry()
        self.assertNotIn("/tmp/definitely-does-not-exist-xyz", reg["installations"])

    def test_cleanup_orphans_keeps_live_paths(self):
        """Installations whose directory still exists are NOT cleaned up."""
        live_dir = Path(self.tmpdir.name) / "live-project"
        live_dir.mkdir()
        reg_mod.register_installation(
            project_path=str(live_dir),
            install_method="manual",
        )
        cleaned = reg_mod.cleanup_orphans()
        self.assertNotIn(str(live_dir), cleaned)
        self.assertIn(str(live_dir), reg_mod.load_registry()["installations"])


class TestRegistryLocking(unittest.TestCase):
    """Test that file locking prevents concurrent corruption."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self._orig_registry_file = reg_mod.REGISTRY_FILE
        self._orig_registry_dir = reg_mod.REGISTRY_DIR
        reg_mod.REGISTRY_DIR = Path(self.tmpdir.name)
        reg_mod.REGISTRY_FILE = reg_mod.REGISTRY_DIR / "registry.json"
        reg_mod.LOCK_FILE = reg_mod.REGISTRY_DIR / ".registry.lock"

    def tearDown(self):
        reg_mod.REGISTRY_FILE = self._orig_registry_file
        reg_mod.REGISTRY_DIR = self._orig_registry_dir
        reg_mod.LOCK_FILE = self._orig_registry_dir / ".registry.lock"
        self.tmpdir.cleanup()

    def test_lock_context_manager(self):
        """_lock_registry acquires and releases without error."""
        with reg_mod._lock_registry():
            reg = reg_mod.load_registry()
            reg["installations"]["test"] = {"x": 1}
            reg_mod.save_registry(reg)
        # Lock released — can read back
        reg2 = reg_mod.load_registry()
        self.assertEqual(reg2["installations"]["test"]["x"], 1)


if __name__ == "__main__":
    unittest.main()
