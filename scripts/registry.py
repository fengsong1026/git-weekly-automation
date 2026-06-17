#!/usr/bin/env python3
"""
git-weekly-automation — Central Registry

Manages a persistent registry at ~/.git-weekly-automation/registry.json
that survives project directory deletion. All setup/schedule operations
read and write this registry to track installed artifacts.

The registry is the authoritative source for:
  - Which projects have been installed
  - What git hooksPath was configured
  - Which launchd scheduled tasks were created

This enables clean uninstallation even if the project directory is deleted
(by reading the registry instead of project-local state).
"""

import fcntl
import json
import os
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REGISTRY_DIR = Path.home() / ".git-weekly-automation"
REGISTRY_FILE = REGISTRY_DIR / "registry.json"
REGISTRY_VERSION = 1
LOCK_FILE = REGISTRY_DIR / ".registry.lock"


# ---------------------------------------------------------------------------
# File locking (prevents read-modify-write races between concurrent processes)
# ---------------------------------------------------------------------------

@contextmanager
def _lock_registry():
    """Acquire an exclusive lock on the registry file for atomic read-modify-write."""
    _ensure_dir()
    lock_fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


# ---------------------------------------------------------------------------
# Core I/O
# ---------------------------------------------------------------------------

def _ensure_dir() -> None:
    """Create the registry directory if it doesn't exist."""
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)


def load_registry() -> dict:
    """
    Load the registry from disk.
    Returns a default empty registry if the file doesn't exist or is corrupt.
    """
    _ensure_dir()
    if not REGISTRY_FILE.exists():
        return _empty_registry()

    try:
        data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
        # Basic validation
        if not isinstance(data, dict):
            return _empty_registry()
        if "installations" not in data or not isinstance(data["installations"], dict):
            data["installations"] = {}
        data.setdefault("version", REGISTRY_VERSION)
        return data
    except (json.JSONDecodeError, OSError):
        return _empty_registry()


def save_registry(registry: dict) -> None:
    """
    Atomically write the registry to disk.
    Uses a temp-file + rename strategy to avoid corruption.
    """
    _ensure_dir()
    registry["version"] = REGISTRY_VERSION
    registry.setdefault("installations", {})

    # Atomic write: write to temp file, then rename
    fd, tmp_path = tempfile.mkstemp(
        dir=str(REGISTRY_DIR),
        prefix=".registry-",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(registry, f, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp_path, str(REGISTRY_FILE))
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _empty_registry() -> dict:
    """Return a new empty registry structure."""
    return {
        "version": REGISTRY_VERSION,
        "installations": {},
    }


# ---------------------------------------------------------------------------
# Installation management
# ---------------------------------------------------------------------------

def register_installation(
    project_path: str,
    install_method: str = "manual",
    hooks_path_set: bool = False,
    original_hooks_path: Optional[str] = None,
) -> dict:
    """
    Register a project installation in the registry.

    Args:
        project_path: Absolute path to the project directory.
        install_method: How the project was installed (manual, npm-global, npm-local).
        hooks_path_set: Whether git global core.hooksPath was configured.
        original_hooks_path: Previous hooksPath value (for restoration on uninstall).

    Returns:
        The updated registry dict.
    """
    with _lock_registry():
        registry = load_registry()
        now = datetime.now(timezone.utc).isoformat()

        existing = registry["installations"].get(project_path, {})

        entry = {
            "install_method": install_method,
            "hooks_path_set": hooks_path_set,
            "original_hooks_path": original_hooks_path,
            "scheduled_tasks": existing.get("scheduled_tasks", {}),
            "installed_at": existing.get("installed_at", now),
            "updated_at": now,
        }

        registry["installations"][project_path] = entry
        save_registry(registry)
        return registry


def unregister_installation(project_path: str) -> dict:
    """
    Remove a project installation from the registry.

    Returns the updated registry dict.
    """
    with _lock_registry():
        registry = load_registry()
        registry["installations"].pop(project_path, None)
        save_registry(registry)
        return registry


def get_installation(project_path: str) -> Optional[dict]:
    """
    Get the registry entry for a specific project path.
    Returns None if not found.
    """
    registry = load_registry()
    return registry["installations"].get(project_path)


def update_installation(project_path: str, **kwargs) -> Optional[dict]:
    """
    Update fields on an existing installation entry.
    Returns the updated entry, or None if not found.
    """
    registry = load_registry()
    entry = registry["installations"].get(project_path)
    if entry is None:
        return None
    entry.update(kwargs)
    entry["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_registry(registry)
    return entry


def list_installations() -> dict:
    """
    Return all registered installations.
    """
    registry = load_registry()
    return registry["installations"]


# ---------------------------------------------------------------------------
# Scheduled task management
# ---------------------------------------------------------------------------

def register_task(
    project_path: str,
    task_name: str,
    label: str,
    plist_path: str,
    schedule: str,
    command: str,
) -> Optional[dict]:
    """
    Register a scheduled task under a project installation.

    Creates the installation entry if it doesn't exist (for projects
    that add tasks without running setup first).
    """
    with _lock_registry():
        registry = load_registry()
        now = datetime.now(timezone.utc).isoformat()

        entry = registry["installations"].get(project_path)
        if entry is None:
            # Auto-create a minimal installation entry
            entry = {
                "install_method": "unknown",
                "hooks_path_set": False,
                "original_hooks_path": None,
                "scheduled_tasks": {},
                "installed_at": now,
                "updated_at": now,
            }
            registry["installations"][project_path] = entry

        entry["scheduled_tasks"][task_name] = {
            "label": label,
            "plist": plist_path,
            "schedule": schedule,
            "command": command,
            "created_at": now,
        }
        entry["updated_at"] = now

        save_registry(registry)
        return entry


def unregister_task(project_path: str, task_name: str) -> Optional[dict]:
    """
    Remove a scheduled task from a project's registry entry.
    Returns the updated entry, or None if the project is not found.
    """
    with _lock_registry():
        registry = load_registry()
        entry = registry["installations"].get(project_path)
        if entry is None:
            return None

        entry["scheduled_tasks"].pop(task_name, None)
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()

        # If no tasks remain and no hooks set, remove the entire installation entry
        if not entry["scheduled_tasks"] and not entry.get("hooks_path_set"):
            registry["installations"].pop(project_path, None)

        save_registry(registry)
        return entry


def clear_tasks(project_path: str) -> Optional[dict]:
    """
    Remove all scheduled tasks from a project's registry entry.
    Returns the updated entry, or None if the project is not found.
    """
    with _lock_registry():
        registry = load_registry()
        entry = registry["installations"].get(project_path)
        if entry is None:
            return None

        entry["scheduled_tasks"] = {}
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()

        # If hooks were never set either, remove the entire entry
        if not entry.get("hooks_path_set"):
            registry["installations"].pop(project_path, None)

        save_registry(registry)
        return entry


# ---------------------------------------------------------------------------
# Orphan management
# ---------------------------------------------------------------------------

def cleanup_orphans() -> list:
    """
    Scan the registry for installations whose project_path no longer exists
    on disk, and remove them. Also cleans up leftover plist files referenced
    by orphaned tasks.

    Returns a list of cleaned-up project paths.
    """
    # Phase 1: find orphans and clean up external artifacts (no lock needed)
    registry_snapshot = load_registry()
    to_clean = []
    for project_path, entry in registry_snapshot["installations"].items():
        if not Path(project_path).is_dir():
            to_clean.append((project_path, entry))

    for project_path, entry in to_clean:
        # Clean up plist files and unload from launchd
        for task_name, task_info in entry.get("scheduled_tasks", {}).items():
            plist_path = task_info.get("plist", "")
            if plist_path and Path(plist_path).exists():
                try:
                    Path(plist_path).unlink()
                except OSError:
                    pass
            label = task_info.get("label", "")
            if label:
                subprocess.run(
                    ["launchctl", "bootout", f"gui/{os.getuid()}/{label}"],
                    capture_output=True,
                )

        # Restore hooksPath if needed
        if entry.get("hooks_path_set") and entry.get("original_hooks_path") is not None:
            current = subprocess.run(
                ["git", "config", "--global", "core.hooksPath"],
                capture_output=True, text=True,
            ).stdout.strip()
            hooks_path = entry.get("hooks_path", project_path + "/hooks")
            if current == hooks_path or current == "":
                original = entry["original_hooks_path"]
                if original:
                    subprocess.run(
                        ["git", "config", "--global", "core.hooksPath", original],
                        capture_output=True,
                    )
                else:
                    subprocess.run(
                        ["git", "config", "--global", "--unset", "core.hooksPath"],
                        capture_output=True,
                    )

    # Phase 2: atomically update registry (under lock)
    if to_clean:
        with _lock_registry():
            registry = load_registry()
            for project_path, _entry in to_clean:
                registry["installations"].pop(project_path, None)
            save_registry(registry)

    return [p for p, _e in to_clean]


# ===================================================================
# CLI: python3 scripts/registry.py <command>
# ===================================================================
if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="git-weekly-automation registry manager")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("list", help="List all installations")
    sub.add_parser("cleanup", help="Remove orphaned installations")
    sub.add_parser("dump", help="Dump full registry as JSON")

    args = parser.parse_args()

    if args.cmd == "list":
        reg = load_registry()
        installs = reg.get("installations", {})
        if not installs:
            print("No installations registered.")
        for path, entry in installs.items():
            task_count = len(entry.get("scheduled_tasks", {}))
            exists = "✓" if Path(path).is_dir() else "✗ (orphaned)"
            print(f"  {exists}  {path}")
            print(f"       method={entry.get('install_method')}, hooks={entry.get('hooks_path_set')}, tasks={task_count}")
            print(f"       installed={entry.get('installed_at', '?')}")

    elif args.cmd == "cleanup":
        print("Scanning for orphaned installations...")
        cleaned = cleanup_orphans()
        if cleaned:
            for path in cleaned:
                print(f"  [✓] Cleaned up: {path}")
            print(f"Removed {len(cleaned)} orphaned installation(s).")
        else:
            print("No orphaned installations found.")

    elif args.cmd == "dump":
        reg = load_registry()
        print(json.dumps(reg, ensure_ascii=False, indent=2))

    else:
        parser.print_help()
