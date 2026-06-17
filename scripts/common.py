#!/usr/bin/env python3
"""
git-weekly-automation — Shared utilities

Functions used across multiple scripts. Import from sibling scripts via:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from common import load_config, get_git_user_email
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
CONFIG_FILE = PROJECT_DIR / "config.json"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """Load project configuration from config.json."""
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def resolve_api_key() -> Optional[str]:
    """Resolve API key with priority: env var > config file."""
    env_key = os.environ.get("OPENAI_API_KEY")
    if env_key:
        return env_key
    config = load_config()
    return config.get("api_key")


# ---------------------------------------------------------------------------
# Git
# ---------------------------------------------------------------------------

def get_git_user_email() -> str:
    """
    Get the global git user email from git config.
    Returns empty string if not set or git is unavailable.
    """
    try:
        result = subprocess.run(
            ["git", "config", "--global", "user.email"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            email = result.stdout.strip()
            if email:
                return email
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return ""


# ---------------------------------------------------------------------------
# ISO week helpers
# ---------------------------------------------------------------------------

def validate_iso_week(week: int) -> int:
    """
    Validate and clamp an ISO week number to 1–53.
    Exits with an error message if out of range.
    """
    if week < 1 or week > 53:
        print(f"[!] Invalid ISO week number: {week}. Must be between 1 and 53.", file=sys.stderr)
        sys.exit(1)
    return week


# ---------------------------------------------------------------------------
# Data retention cleanup
# ---------------------------------------------------------------------------

def purge_old_data(config: Optional[dict] = None) -> dict:
    """
    Purge old data files per retention settings in config.json cleanup block.

    Defaults (if no config or key missing):
        commits_weeks: 52  — delete JSONL files older than 52 weeks
        reports_weeks: 26  — delete report .md files older than 26 weeks
        logs_days:     90  — delete log files older than 90 days

    Returns a dict with counts of deleted files per category.
    """
    if config is None:
        config = load_config()

    cleanup_cfg = config.get("cleanup", {})
    if not isinstance(cleanup_cfg, dict):
        cleanup_cfg = {}

    commits_weeks = cleanup_cfg.get("commits_weeks", 52)
    reports_weeks = cleanup_cfg.get("reports_weeks", 26)
    logs_days = cleanup_cfg.get("logs_days", 90)

    now = datetime.now(timezone.utc)
    deleted = {"commits": 0, "reports": 0, "logs": 0}

    # --- Purge old commit JSONL files ---
    commits_dir = PROJECT_DIR / "data" / "commits"
    if commits_dir.is_dir() and commits_weeks > 0:
        cutoff = now - timedelta(weeks=commits_weeks)
        for f in commits_dir.glob("*.jsonl"):
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                if mtime < cutoff:
                    f.unlink()
                    deleted["commits"] += 1
            except OSError:
                pass

    # --- Purge old report files ---
    reports_dir = PROJECT_DIR / "reports"
    if reports_dir.is_dir() and reports_weeks > 0:
        cutoff = now - timedelta(weeks=reports_weeks)
        for f in reports_dir.glob("*.md"):
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                if mtime < cutoff:
                    f.unlink()
                    deleted["reports"] += 1
            except OSError:
                pass

    # --- Purge old log files ---
    logs_dir = PROJECT_DIR / "data" / "logs"
    if logs_dir.is_dir() and logs_days > 0:
        cutoff = now - timedelta(days=logs_days)
        for f in logs_dir.iterdir():
            if f.is_file():
                try:
                    mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                    if mtime < cutoff:
                        f.unlink()
                        deleted["logs"] += 1
                except OSError:
                    pass

    if any(deleted.values()):
        parts = []
        if deleted["commits"]:
            parts.append(f"{deleted['commits']} commit files")
        if deleted["reports"]:
            parts.append(f"{deleted['reports']} reports")
        if deleted["logs"]:
            parts.append(f"{deleted['logs']} log files")
        print(f"[*] Cleanup: removed {', '.join(parts)} (retention policy)")

    return deleted
